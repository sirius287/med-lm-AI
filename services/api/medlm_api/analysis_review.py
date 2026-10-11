"""Explicit synthetic human review with independent verification and image retention."""

import hashlib
from datetime import datetime
from uuid import UUID

from medlm_domain.analysis import Contract, ExtractionResult, Verification
from medlm_domain.review import (
    Decision,
    HumanReview,
    ReviewTarget,
    accepted_values,
    observed_fields,
    validate_review,
)

from medlm_api.analysis_repository import AnalysisRepository
from medlm_api.domain_idempotency import canonical
from medlm_api.errors import AppError
from medlm_api.uploads import queue_delete, sql


class ReviewReceipt(Contract):
    id: UUID
    analysis_id: UUID
    revision: int
    candidate_set_id: UUID
    version: int
    decision: Decision
    final: bool
    created_at: datetime
    verification: Verification
    accepted_values: dict[str, str | None]


class ReviewContext(Contract):
    analysis_id: UUID
    version: int
    revision: int
    candidate_set_id: UUID
    candidates: tuple[()] = ()
    extraction: ExtractionResult
    required_field_keys: tuple[str, ...]
    closed: bool
    image_available: bool
    expires_at: datetime
    verification: Verification
    history: tuple[ReviewReceipt, ...]


class HumanReviews:
    def __init__(self, lifecycle):
        self.lifecycle = lifecycle

    def target(self, conn, principal, identity, revision=None):
        a, upload = self.lifecycle.load(conn, principal, identity)
        row = (
            sql(
                conn,
                """SELECT er.* FROM medlm.extraction_revisions er
            JOIN medlm.analysis_jobs j ON (j.user_id,j.id)=(er.user_id,er.job_id)
            WHERE er.user_id=:u AND er.id=:r AND er.job_id=:job AND j.state='completed'""",
                u=principal.user_id,
                r=a["current_revision_id"],
                job=a["current_job_id"],
            )
            .mappings()
            .first()
        )
        if row is None or (revision is not None and row["revision"] != revision):
            raise AppError(409, "stale_revision", "Review requires the current completed revision.")
        return a, upload, row, ExtractionResult.model_validate(row["observations"])

    @staticmethod
    def receipt(row, revision, extraction):
        body = HumanReview(
            version=row["analysis_version"],
            revision=revision,
            candidate_set_id=row["candidate_set_id"],
            decision=row["decision"],
            fields=row["fields"],
            line_dispositions=row["line_dispositions"],
        )
        return ReviewReceipt(
            id=row["id"],
            analysis_id=row["analysis_id"],
            revision=revision,
            candidate_set_id=row["candidate_set_id"],
            version=row["analysis_version"] + 1,
            decision=row["decision"],
            final=row["decision"] != "unresolved",
            created_at=row["created_at"],
            verification=Verification(status="unverified"),
            accepted_values=accepted_values(body, extraction),
        )

    def context(self, conn, principal, a, upload, row, extraction):
        candidate_set = sql(
            conn,
            """SELECT id FROM medlm.identity_candidate_sets
            WHERE user_id=:u AND extraction_revision_id=:r""",
            u=principal.user_id,
            r=row["id"],
        ).scalar()
        if candidate_set is None:
            raise AppError(409, "review_not_prepared", "Prepare the review first.")
        history = (
            sql(
                conn,
                """SELECT * FROM medlm.analysis_reviews WHERE user_id=:u
            AND extraction_revision_id=:r AND review_schema_version=1 ORDER BY analysis_version""",
                u=principal.user_id,
                r=row["id"],
            )
            .mappings()
            .all()
        )
        return ReviewContext(
            analysis_id=a["id"],
            version=a["version"],
            revision=row["revision"],
            candidate_set_id=candidate_set,
            extraction=extraction,
            required_field_keys=tuple(observed_fields(extraction)),
            closed=any(r["decision"] != "unresolved" for r in history),
            image_available=bool(
                upload
                and upload.status == "accepted"
                and not a["cancelled_at"]
                and not a["expired_at"]
                and a["expires_at"] > self.lifecycle.uploads.clock()
            ),
            expires_at=a["expires_at"],
            verification=Verification(status="unverified"),
            history=tuple(self.receipt(r, row["revision"], extraction) for r in history),
        )

    def get(self, db, principal, identity):
        # Saved review text is separate from image availability/retention.
        with self.lifecycle.owned(db, principal) as conn:
            return self.context(conn, principal, *self.target(conn, principal, identity))

    def prepare(self, db, principal, identity, body: ReviewTarget, key):
        self.lifecycle.refresh(db, principal, identity)
        with self.lifecycle.owned(db, principal) as conn:
            a, upload, row, extraction = self.target(conn, principal, identity, body.revision)
            self.lifecycle.available(a, upload)
            self.lifecycle.version(a["version"], body.version)

            def action():
                AnalysisRepository(conn, principal.user_id).prepare_review(
                    identity, row["id"], extraction
                )
                return self.context(conn, principal, a, upload, row, extraction).model_dump(
                    mode="json"
                ), identity

            return self.lifecycle.replay(
                conn,
                principal,
                f"{identity}:review-prepare",
                key,
                body.model_dump(mode="json"),
                action,
            )

    def submit(self, db, principal, identity, body: HumanReview, key):
        try:
            request_key = UUID(key or "")
        except ValueError:
            raise AppError(428, "idempotency_required", "A request key is required.") from None
        payload = body.model_dump(mode="json")
        digest = hashlib.sha256(canonical(payload).encode()).hexdigest()
        # Refresh commits expiry cleanup. Receipt replay is independent of image deletion.
        self.lifecycle.refresh(db, principal, identity)
        with self.lifecycle.owned(db, principal) as conn:
            a, upload, row, extraction = self.target(conn, principal, identity, body.revision)
            prior = (
                sql(
                    conn,
                    """SELECT * FROM medlm.analysis_reviews WHERE user_id=:u
                AND analysis_id=:a AND request_key=:k AND review_schema_version=1""",
                    u=principal.user_id,
                    a=identity,
                    k=request_key,
                )
                .mappings()
                .first()
            )
            if prior:
                if prior["request_sha256"] != digest:
                    raise AppError(
                        409, "idempotency_conflict", "Use a new request key for changed input."
                    )
                return self.receipt(prior, row["revision"], extraction)
            closed = sql(
                conn,
                """SELECT 1 FROM medlm.analysis_reviews WHERE user_id=:u AND analysis_id=:a
                AND review_schema_version=1 AND decision<>'unresolved'""",
                u=principal.user_id,
                a=identity,
            ).first()
            if closed:
                raise AppError(409, "review_closed", "Final reviews cannot be edited or reopened.")
            self.lifecycle.available(a, upload)
            self.lifecycle.version(a["version"], body.version)
            candidate_set = sql(
                conn,
                """SELECT id FROM medlm.identity_candidate_sets
                WHERE user_id=:u AND analysis_id=:a AND extraction_revision_id=:r AND id=:s
                AND NOT EXISTS(SELECT 1 FROM medlm.identity_candidates WHERE candidate_set_id=:s)""",
                u=principal.user_id,
                a=identity,
                r=row["id"],
                s=body.candidate_set_id,
            ).scalar()
            if candidate_set is None:
                raise AppError(409, "stale_candidate_set", "Reload the current review context.")
            try:
                validate_review(body, extraction)
            except ValueError as exc:
                raise AppError(422, "invalid_review", str(exc)) from None

            def action():
                review = AnalysisRepository(conn, principal.user_id).append_review(
                    identity, row["id"], body, request_key, digest
                )
                sql(
                    conn,
                    "UPDATE medlm.medicine_analyses SET version=version+1 WHERE user_id=:u AND id=:a",
                    u=principal.user_id,
                    a=identity,
                )
                if body.decision != "unresolved":
                    queue_delete(conn, upload, "completed")
                return self.receipt(review, row["revision"], extraction).model_dump(
                    mode="json"
                ), identity

            return self.lifecycle.replay(
                conn, principal, f"{identity}:review-submit", key, payload, action
            )

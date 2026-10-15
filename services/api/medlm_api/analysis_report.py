"""Read-only projection from one owner-locked saved-text snapshot."""

from medlm_domain.analysis import SyntheticProvenance
from medlm_domain.extraction import ExtractionMetadata
from medlm_domain.report import ReviewedTranscription, assemble_report
from medlm_domain.review import HumanReview
from pydantic import ValidationError

from medlm_api.analysis_review import HumanReviews
from medlm_api.errors import AppError
from medlm_api.uploads import sql


class _InvalidReportInput(ValueError):
    """An explicitly detected invalid persisted report input."""


class SyntheticReports:
    def __init__(self, lifecycle):
        self.lifecycle = lifecycle

    def get(self, db, principal, identity, revision):
        # Do not call refresh/available: saved text survives image expiry/cancellation.
        # Parent lock serializes retry, review and erasure. No snapshot crosses a transaction.
        with self.lifecycle.owned(db, principal) as conn:
            try:
                a, upload, row, observations = HumanReviews(self.lifecycle).target(
                    conn, principal, identity, revision
                )
            except ValidationError:
                # Authorization/current-revision AppErrors and database/programming
                # errors propagate unchanged; only stored contract validation maps here.
                raise AppError(
                    409, "report_unavailable", "Saved report input is unavailable."
                ) from None
            records = (
                sql(
                    conn,
                    """SELECT r.* FROM medlm.analysis_reviews r
                JOIN medlm.identity_candidate_sets s
                  ON (s.user_id,s.analysis_id,s.extraction_revision_id,s.id)=
                     (r.user_id,r.analysis_id,r.extraction_revision_id,r.candidate_set_id)
                WHERE r.user_id=:u AND r.analysis_id=:a AND r.extraction_revision_id=:r
                ORDER BY r.analysis_version""",
                    u=principal.user_id,
                    a=identity,
                    r=row["id"],
                )
                .mappings()
                .all()
            )
            try:
                history = []
                closed, previous = False, 0
                for record in records:
                    if (
                        closed
                        or record["review_schema_version"] != 1
                        or record["candidate_id"] is not None
                        or not previous < record["analysis_version"] < a["version"]
                    ):
                        raise _InvalidReportInput("Ineligible review history")
                    history.append(
                        ReviewedTranscription(
                            id=record["id"],
                            review=HumanReview(
                                version=record["analysis_version"],
                                revision=row["revision"],
                                candidate_set_id=record["candidate_set_id"],
                                decision=record["decision"],
                                fields=record["fields"],
                                line_dispositions=record["line_dispositions"],
                            ),
                        )
                    )
                    previous = record["analysis_version"]
                    closed = record["decision"] != "unresolved"
                expired = bool(a["expired_at"] or a["expires_at"] <= self.lifecycle.uploads.clock())
                if row["provenance"] != "synthetic" or row["verification"] != "unverified":
                    raise _InvalidReportInput("Unsupported provenance")
                return assemble_report(
                    analysis_id=a["id"],
                    analysis_version=a["version"],
                    extraction_revision_id=row["id"],
                    revision=row["revision"],
                    country=a["country"],
                    locale=a["locale"],
                    observations=observations,
                    provenance=SyntheticProvenance(
                        fixture_id=row["fixture_id"], source_sha256=row["fixture_sha256"]
                    ),
                    extraction_metadata=ExtractionMetadata(
                        **{key: row[key] for key in ExtractionMetadata.model_fields}
                    ),
                    review_history=tuple(history),
                    image_available=bool(
                        upload
                        and upload.status == "accepted"
                        and not expired
                        and not a["cancelled_at"]
                    ),
                    original_expires_at=a["expires_at"],
                    expired=expired,
                    cancelled=bool(a["cancelled_at"]),
                )
            except (_InvalidReportInput, ValidationError):
                raise AppError(
                    409, "report_unavailable", "Saved report input is unavailable."
                ) from None

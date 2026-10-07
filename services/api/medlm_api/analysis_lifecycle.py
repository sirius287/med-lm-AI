"""Authenticated synthetic lifecycle only. No execution or extraction provider."""

from contextlib import contextmanager
from datetime import timedelta
from uuid import UUID, uuid4

from medlm_domain.analysis import AnalysisState, transition

from medlm_api.analysis_repository import AnalysisRepository
from medlm_api.domain_idempotency import idempotent
from medlm_api.errors import AppError
from medlm_api.uploads import queue_delete, sql

TERMINAL = {"completed", "failed", "cancelled", "needs_input"}


class SyntheticAnalyses:
    def __init__(self, uploads, encryption_key, *, lease_seconds=30):
        if encryption_key is None or not 1 <= lease_seconds <= 60:
            raise ValueError("Existing replay encryption and bounded lease required")
        self.uploads, self.key, self.lease_seconds = uploads, encryption_key, lease_seconds

    @contextmanager
    def owned(self, db, principal):
        # Reuse upload session/account expiry checks and logout lock, then the
        # existing per-user domain replay lock. No network work inside this scope.
        with self.uploads.owned(db, principal) as conn:
            sql(
                conn,
                "SELECT pg_advisory_xact_lock(hashtextextended(:u,5))",
                u=str(principal.user_id),
            )
            sql(
                conn,
                "SELECT set_config('app.analysis_session_id',:s,true)",
                s=str(principal.session_id),
            )
            yield conn

    def load(self, conn, principal, identity):
        a = (
            sql(
                conn,
                """SELECT * FROM medlm.medicine_analyses WHERE user_id=:u AND id=:a
          AND analysis_mode='synthetic' AND expires_at IS NOT NULL FOR UPDATE""",
                u=principal.user_id,
                a=identity,
            )
            .mappings()
            .first()
        )
        if a is None:
            raise AppError(404, "not_found", "Analysis is unavailable.")
        upload = sql(
            conn,
            """SELECT u.* FROM medlm.uploads u JOIN medlm.analysis_uploads l
          ON (l.user_id,l.upload_id)=(u.user_id,u.id)
          WHERE l.user_id=:u AND l.analysis_id=:a FOR UPDATE OF u""",
            u=principal.user_id,
            a=identity,
        ).first()
        return a, upload

    def view(self, conn, a, upload):
        availability = "available"
        if a["expired_at"] or a["expires_at"] <= self.uploads.clock():
            availability = "expired"
        elif a["cancelled_at"]:
            availability = "cancelled"
        elif upload is None or upload.status != "accepted":
            availability = "unavailable"
        j = (
            sql(conn, "SELECT * FROM medlm.analysis_jobs WHERE id=:j", j=a["current_job_id"])
            .mappings()
            .one()
        )
        revision = sql(
            conn,
            "SELECT revision FROM medlm.extraction_revisions WHERE id=:r",
            r=a["current_revision_id"],
        ).scalar()
        return dict(
            id=a["id"],
            version=a["version"],
            availability=availability,
            expires_at=a["expires_at"],
            expired_at=a["expired_at"],
            result_revision=revision,
            job=dict(
                id=j["id"],
                attempt=j["attempt"],
                state=j["state"],
                version=j["lifecycle_version"],
                fencing_token=j["fencing_token"],
                lease_expires_at=j["lease_until"],
            ),
        )

    def refresh(self, db, principal, identity):
        # Commit deadline cleanup before returning a later 410 from a mutation.
        # Independent upload maintenance still purges when no API request occurs.
        with self.owned(db, principal) as conn:
            a, upload = self.load(conn, principal, identity)
            if a["expires_at"] <= self.uploads.clock():
                if not a["expired_at"] and not a["cancelled_at"]:
                    sql(
                        conn,
                        """UPDATE medlm.medicine_analyses SET expired_at=clock_timestamp(),
                      version=version+1 WHERE id=:a""",
                        a=identity,
                    )
                if upload is not None:
                    queue_delete(conn, upload, "expiry")
                a, upload = self.load(conn, principal, identity)
            return self.view(conn, a, upload)

    def available(self, a, upload):
        if a["expired_at"] or a["expires_at"] <= self.uploads.clock():
            raise AppError(410, "analysis_expired", "Analysis has expired.")
        if a["cancelled_at"] or upload is None or upload.status != "accepted":
            raise AppError(410, "analysis_unavailable", "Analysis is unavailable.")

    def replay(self, conn, principal, operation, key, body, action):
        return idempotent(
            conn, principal.user_id, "analysis:" + operation, key, body, self.key, action
        )

    def create(self, db, principal, body, key):
        with self.owned(db, principal) as conn:
            upload = self.uploads.row(conn, body.upload_id, active=True)
            self.uploads.health(conn)
            if (
                upload.status != "accepted"
                or not upload.retain_for_review
                or upload.document_kind != body.document_kind
                or upload.mime != body.content_type
                or upload.source_checksum_sha256 not in self.uploads.allowed
            ):
                raise AppError(
                    422, "analysis_upload_invalid", "Use an accepted retained synthetic upload."
                )

            def action():
                if sql(
                    conn, "SELECT 1 FROM medlm.analysis_uploads WHERE upload_id=:u", u=upload.id
                ).first():
                    raise AppError(409, "analysis_exists", "This upload already has an analysis.")
                repo = AnalysisRepository(conn, principal.user_id)
                a = repo.create(
                    kind="prescription" if body.document_kind == "prescription" else "medicine",
                    locale=body.locale,
                    expires_at=upload.expires_at,
                )
                sql(
                    conn,
                    """INSERT INTO medlm.analysis_uploads(id,user_id,analysis_id,upload_id)
                  VALUES (:id,:u,:a,:upload)""",
                    id=uuid4(),
                    u=principal.user_id,
                    a=a,
                    upload=upload.id,
                )
                repo.start_attempt(a, 1, UUID(key), origin_session_id=principal.session_id)
                parent, current = self.load(conn, principal, a)
                return self.view(conn, parent, current), a

            return self.replay(conn, principal, "create", key, body.model_dump(mode="json"), action)

    @staticmethod
    def version(actual, expected):
        if actual != expected:
            raise AppError(409, "stale_version", "Reload the current analysis status.")

    def mutate(self, db, principal, identity, operation, key, body, job_id=None):
        self.refresh(db, principal, identity)
        with self.owned(db, principal) as conn:
            a, upload = self.load(conn, principal, identity)
            if operation != "cancel" or not a["cancelled_at"]:
                self.available(a, upload)
            if job_id is not None and job_id != a["current_job_id"]:
                raise AppError(409, "stale_job", "This job has been superseded.")

            def action():
                repo = AnalysisRepository(conn, principal.user_id)
                if operation in ("retry", "cancel"):
                    if operation == "cancel" and a["cancelled_at"]:
                        return self.view(conn, a, upload), identity
                    self.version(a["version"], body.version)
                    if operation == "retry":
                        self.uploads.health(conn)
                        repo.start_attempt(
                            identity,
                            a["version"],
                            UUID(key),
                            origin_session_id=principal.session_id,
                        )
                    else:
                        # Stable cancellation freezes all attempts, even unleased jobs.
                        repo.cancel(identity, a["version"])
                        queue_delete(conn, upload, "cancelled")
                else:
                    j = (
                        sql(
                            conn,
                            "SELECT * FROM medlm.analysis_jobs WHERE id=:j FOR UPDATE",
                            j=job_id,
                        )
                        .mappings()
                        .one()
                    )
                    if j["origin_session_id"] != principal.session_id:
                        raise AppError(403, "job_session", "Create a new attempt for this session.")
                    self.version(j["lifecycle_version"], body.job_version)
                    if j["state"] in TERMINAL:
                        raise AppError(409, "terminal_job", "Terminal jobs cannot change.")
                    now = self.uploads.clock()
                    if operation == "lease":
                        if j["lease_until"] and j["lease_until"] > now:
                            raise AppError(409, "lease_active", "A current lease already exists.")
                        token = uuid4()
                        sql(
                            conn,
                            """UPDATE medlm.analysis_jobs SET lease_token=:token,lease_until=:until,
                          fencing_token=fencing_token+1,lifecycle_version=lifecycle_version+1 WHERE id=:j""",
                            token=token,
                            until=min(a["expires_at"], now + timedelta(seconds=self.lease_seconds)),
                            j=job_id,
                        )
                    elif operation == "transition":
                        if (
                            j["lease_token"] != body.lease_token
                            or j["fencing_token"] != body.fencing_token
                            or not j["lease_until"]
                            or j["lease_until"] <= now
                        ):
                            raise AppError(
                                409, "stale_lease", "The job lease is no longer current."
                            )
                        try:
                            transition(AnalysisState(j["state"]), AnalysisState(body.target))
                        except ValueError as exc:
                            raise AppError(
                                409, "invalid_transition", "Job transition is not permitted."
                            ) from exc
                        sql(
                            conn,
                            """SELECT set_config('app.analysis_lease_token',:t,true),
                          set_config('app.analysis_fence',:f,true)""",
                            t=str(body.lease_token),
                            f=str(body.fencing_token),
                        )
                        terminal = body.target in TERMINAL
                        sql(
                            conn,
                            """UPDATE medlm.analysis_jobs SET state=:state,
                          lease_token=CASE WHEN :terminal THEN NULL ELSE lease_token END,
                          lease_until=CASE WHEN :terminal THEN NULL ELSE lease_until END,
                          lifecycle_version=lifecycle_version+1 WHERE id=:j""",
                            state=body.target,
                            terminal=terminal,
                            j=job_id,
                        )
                        if body.target == "cancelled":
                            repo.cancel(identity, a["version"])
                            queue_delete(conn, upload, "cancelled")
                parent, current = self.load(conn, principal, identity)
                result = self.view(conn, parent, current)
                if operation == "lease":
                    result["lease_token"] = token
                return result, identity

            return self.replay(
                conn,
                principal,
                f"{identity}:{operation}:{job_id or ''}",
                key,
                body.model_dump(mode="json"),
                action,
            )

"""Owner-scoped persistence primitives used by the synthetic lifecycle harness.

Caller supplies an existing owner-scoped transaction. Publication is atomic with
that transaction; no provider work or automatic acceptance takes place here.
"""

from uuid import UUID, uuid4

from medlm_domain.analysis import ExtractionResult, SyntheticProvenance
from medlm_domain.extraction import ExtractionMetadata
from medlm_domain.review import HumanReview
from sqlalchemy import text
from sqlalchemy.engine import Connection


class AnalysisConflict(ValueError):
    """Unavailable, cancelled or concurrently changed analysis."""


class AnalysisRepository:
    def __init__(self, connection: Connection, user_id: UUID):
        self.connection = connection
        self.user_id = user_id

    def _locked(self, analysis_id: UUID, expected_version: int):
        row = (
            self.connection.execute(
                text("""SELECT * FROM medlm.medicine_analyses
            WHERE user_id=:u AND id=:a AND analysis_mode='synthetic' FOR UPDATE"""),
                {"u": self.user_id, "a": analysis_id},
            )
            .mappings()
            .one_or_none()
        )
        if row is None or row["cancelled_at"] is not None or row["version"] != expected_version:
            raise AnalysisConflict("Analysis unavailable or stale")
        return row

    def create(self, *, kind: str, locale: str, expires_at=None) -> UUID:
        if kind not in {"medicine", "prescription"} or locale not in {"en-IN", "hi-IN", "te-IN"}:
            raise ValueError("Unsupported synthetic analysis context")
        identity = uuid4()
        if expires_at is not None:
            self.connection.execute(
                text("""INSERT INTO medlm.medicine_analyses
              (id,user_id,kind,country,locale,analysis_mode,expires_at)
              VALUES (:id,:u,:kind,'IN',:locale,'synthetic',:expiry)"""),
                {
                    "id": identity,
                    "u": self.user_id,
                    "kind": kind,
                    "locale": locale,
                    "expiry": expires_at,
                },
            )
            return identity
        self.connection.execute(
            text("""INSERT INTO medlm.medicine_analyses
            (id,user_id,kind,country,locale,analysis_mode)
            VALUES (:id,:u,:kind,'IN',:locale,'synthetic')"""),
            {"id": identity, "u": self.user_id, "kind": kind, "locale": locale},
        )
        return identity

    def start_attempt(
        self,
        analysis_id: UUID,
        expected_version: int,
        request_key: UUID,
        *,
        origin_session_id: UUID | None = None,
    ) -> UUID:
        self._locked(analysis_id, expected_version)
        identity = uuid4()
        if origin_session_id is not None:
            self.connection.execute(
                text("""INSERT INTO medlm.analysis_jobs
              (id,user_id,analysis_id,attempt,request_key,origin_session_id)
              SELECT :id,:u,:a,COALESCE(max(attempt),0)+1,:key,:session
              FROM medlm.analysis_jobs WHERE user_id=:u AND analysis_id=:a"""),
                {
                    "id": identity,
                    "u": self.user_id,
                    "a": analysis_id,
                    "key": request_key,
                    "session": origin_session_id,
                },
            )
        else:
            self.connection.execute(
                text("""INSERT INTO medlm.analysis_jobs(id,user_id,analysis_id,attempt,request_key)
            SELECT :id,:u,:a,COALESCE(max(attempt),0)+1,:key
            FROM medlm.analysis_jobs WHERE user_id=:u AND analysis_id=:a"""),
                {"id": identity, "u": self.user_id, "a": analysis_id, "key": request_key},
            )
        self.connection.execute(
            text("""UPDATE medlm.medicine_analyses SET current_job_id=:job,version=version+1
            WHERE user_id=:u AND id=:a"""),
            {"job": identity, "u": self.user_id, "a": analysis_id},
        )
        return identity

    def publish(
        self,
        analysis_id: UUID,
        job_id: UUID,
        expected_version: int,
        extraction: ExtractionResult,
        provenance: SyntheticProvenance,
        *,
        lease_token: UUID | None = None,
        fencing_token: int | None = None,
        session_id: UUID | None = None,
        metadata: ExtractionMetadata | None = None,
    ) -> UUID:
        row = self._locked(analysis_id, expected_version)
        if row["current_job_id"] != job_id:
            raise AnalysisConflict("Superseded job")
        managed = row.get("expires_at") is not None
        if managed:
            if lease_token is None or fencing_token is None or session_id is None:
                raise AnalysisConflict("Current lease and session required")
            self.connection.execute(
                text("""SELECT
              set_config('app.analysis_lease_token',:token,true),
              set_config('app.analysis_fence',:fence,true),
              set_config('app.analysis_session_id',:session,true)"""),
                {
                    "token": str(lease_token),
                    "fence": str(fencing_token),
                    "session": str(session_id),
                },
            )
        if (extraction.document_kind == "prescription") != (row["kind"] == "prescription"):
            raise ValueError("Extraction kind differs from analysis")
        identity = uuid4()
        extra_columns = ""
        extra_values = ""
        extra_params = {}
        if metadata is not None:
            metadata = ExtractionMetadata.model_validate(metadata.model_dump())
            extra_params = metadata.model_dump()
            extra_columns = "," + ",".join(extra_params)
            extra_values = "," + ",".join(":" + key for key in extra_params)
        self.connection.execute(
            text(f"""INSERT INTO medlm.extraction_revisions
            (id,user_id,analysis_id,job_id,revision,observations,fixture_id,fixture_sha256{extra_columns})
            SELECT :id,:u,:a,:job,COALESCE(max(revision),0)+1,CAST(:data AS jsonb),:fixture,:hash{extra_values}
            FROM medlm.extraction_revisions WHERE user_id=:u AND analysis_id=:a"""),
            {
                "id": identity,
                "u": self.user_id,
                "a": analysis_id,
                "job": job_id,
                "data": extraction.model_dump_json(),
                "fixture": provenance.fixture_id,
                "hash": provenance.source_sha256,
                **extra_params,
            },
        )
        self.connection.execute(
            text("""UPDATE medlm.medicine_analyses SET current_revision_id=:r,version=version+1
            WHERE user_id=:u AND id=:a"""),
            {"r": identity, "u": self.user_id, "a": analysis_id},
        )
        if managed:
            self.connection.execute(
                text("""UPDATE medlm.analysis_jobs SET state='completed',
              lease_token=NULL,lease_until=NULL,lifecycle_version=lifecycle_version+1
              WHERE user_id=:u AND analysis_id=:a AND id=:j"""),
                {"u": self.user_id, "a": analysis_id, "j": job_id},
            )
        else:
            self.connection.execute(
                text("""UPDATE medlm.analysis_jobs SET state='completed'
            WHERE user_id=:u AND analysis_id=:a AND id=:j"""),
                {"u": self.user_id, "a": analysis_id, "j": job_id},
            )
        return identity

    def cancel(self, analysis_id: UUID, expected_version: int) -> None:
        self._locked(analysis_id, expected_version)
        self.connection.execute(
            text("""UPDATE medlm.medicine_analyses SET cancelled_at=now(),version=version+1
            WHERE user_id=:u AND id=:a"""),
            {"u": self.user_id, "a": analysis_id},
        )

    def prepare_review(self, analysis_id, revision_id, extraction):
        """Called under the existing stable-parent lock; never fabricates candidates."""
        params = {"u": self.user_id, "a": analysis_id, "r": revision_id}
        candidate_set = self.connection.scalar(
            text(
                "SELECT id FROM medlm.identity_candidate_sets WHERE user_id=:u AND extraction_revision_id=:r"
            ),
            params,
        )
        if candidate_set is None:
            candidate_set = uuid4()
            self.connection.execute(
                text("""INSERT INTO medlm.identity_candidate_sets
                (id,user_id,analysis_id,extraction_revision_id) VALUES (:id,:u,:a,:r)"""),
                params | {"id": candidate_set},
            )
        if extraction.document_kind == "prescription":
            draft = self.connection.scalar(
                text(
                    "SELECT id FROM medlm.analysis_prescription_drafts WHERE user_id=:u AND analysis_id=:a"
                ),
                params,
            )
            if draft is None:
                draft, prescription = uuid4(), uuid4()
                self.connection.execute(
                    text(
                        "INSERT INTO medlm.prescriptions(id,user_id,analysis_id) VALUES (:id,:u,:a)"
                    ),
                    params | {"id": prescription},
                )
                self.connection.execute(
                    text("""INSERT INTO medlm.analysis_prescription_drafts
                    (id,user_id,analysis_id,prescription_id) VALUES (:id,:u,:a,:p)"""),
                    params | {"id": draft, "p": prescription},
                )
            pr = self.connection.scalar(
                text("""SELECT id FROM medlm.analysis_prescription_revisions
                WHERE user_id=:u AND extraction_revision_id=:r"""),
                params,
            )
            if pr is None:
                pr = uuid4()
                self.connection.execute(
                    text("""INSERT INTO medlm.analysis_prescription_revisions
                    (id,user_id,analysis_id,draft_id,extraction_revision_id,revision)
                    SELECT :id,:u,:a,:d,:r,COALESCE(max(revision),0)+1
                    FROM medlm.analysis_prescription_revisions WHERE user_id=:u AND draft_id=:d"""),
                    params | {"id": pr, "d": draft},
                )
                for line in extraction.lines:
                    self.connection.execute(
                        text("""INSERT INTO medlm.analysis_prescription_lines
                        (id,user_id,analysis_id,draft_id,prescription_revision_id,ordinal,fields,source_line_id)
                        VALUES (:id,:u,:a,:d,:pr,:ordinal,CAST(:fields AS jsonb),:source)"""),
                        params
                        | {
                            "id": uuid4(),
                            "d": draft,
                            "pr": pr,
                            "ordinal": line.ordinal,
                            "fields": line.fields.model_dump_json(),
                            "source": line.line_id,
                        },
                    )
        return candidate_set

    def append_review(self, analysis_id, revision_id, body: HumanReview, key, digest):
        import json

        params = {"u": self.user_id, "a": analysis_id, "r": revision_id}
        if body.decision != "unresolved":
            pr = (
                self.connection.execute(
                    text("""SELECT * FROM medlm.analysis_prescription_revisions
                WHERE user_id=:u AND extraction_revision_id=:r"""),
                    params,
                )
                .mappings()
                .first()
            )
            if pr is not None:
                confirmation = uuid4()
                self.connection.execute(
                    text("""INSERT INTO medlm.analysis_prescription_confirmations
                    (id,user_id,analysis_id,draft_id,prescription_revision_id,request_key,analysis_version,reviewed_fields)
                    VALUES (:id,:u,:a,:d,:pr,:key,:v,CAST(:fields AS jsonb))"""),
                    params
                    | {
                        "id": confirmation,
                        "d": pr["draft_id"],
                        "pr": pr["id"],
                        "key": key,
                        "v": body.version,
                        "fields": json.dumps(
                            {
                                "decision": body.decision,
                                "fields": {k: v.model_dump() for k, v in body.fields.items()},
                            }
                        ),
                    },
                )
                lines = (
                    self.connection.execute(
                        text("""SELECT * FROM medlm.analysis_prescription_lines
                    WHERE user_id=:u AND prescription_revision_id=:pr ORDER BY ordinal"""),
                        params | {"pr": pr["id"]},
                    )
                    .mappings()
                    .all()
                )
                for line in lines:
                    source = line["source_line_id"]
                    self.connection.execute(
                        text("""INSERT INTO medlm.analysis_prescription_confirmation_lines
                        (id,user_id,analysis_id,draft_id,prescription_revision_id,confirmation_id,
                          line_id,disposition,reviewed_fields)
                        VALUES (:id,:u,:a,:d,:pr,:c,:line,:disposition,CAST(:fields AS jsonb))"""),
                        params
                        | {
                            "id": uuid4(),
                            "d": pr["draft_id"],
                            "pr": pr["id"],
                            "c": confirmation,
                            "line": line["id"],
                            "disposition": body.line_dispositions[source],
                            "fields": json.dumps(
                                {
                                    k.split(".", 1)[1]: v.model_dump()
                                    for k, v in body.fields.items()
                                    if k.startswith(str(source) + ".")
                                }
                            ),
                        },
                    )
        return (
            self.connection.execute(
                text("""INSERT INTO medlm.analysis_reviews
            (id,user_id,analysis_id,extraction_revision_id,candidate_set_id,candidate_id,
              request_key,analysis_version,decision,fields,review_schema_version,request_sha256,line_dispositions)
            VALUES (:id,:u,:a,:r,:s,NULL,:key,:v,:decision,CAST(:fields AS jsonb),1,:hash,CAST(:lines AS jsonb))
            RETURNING *"""),
                params
                | {
                    "id": uuid4(),
                    "s": body.candidate_set_id,
                    "key": key,
                    "v": body.version,
                    "decision": body.decision,
                    "hash": digest,
                    "fields": json.dumps({k: v.model_dump() for k, v in body.fields.items()}),
                    "lines": json.dumps({str(k): v for k, v in body.line_dispositions.items()}),
                },
            )
            .mappings()
            .one()
        )

    def erase(self, analysis_id: UUID, expected_version: int) -> None:
        # Erases saved text only. Upload inventory/deletion jobs are deliberately untouched.
        row = self.connection.execute(
            text("""SELECT version FROM medlm.medicine_analyses WHERE user_id=:u AND id=:a
            AND analysis_mode='synthetic' FOR UPDATE"""),
            {"u": self.user_id, "a": analysis_id},
        ).one_or_none()
        if row is None or row.version != expected_version:
            raise AnalysisConflict("Analysis unavailable or stale")
        # Replay responses contain extraction/review text too. Reuse the existing
        # erasure marker without retaining that text or extending request expiry.
        self.connection.execute(
            text("""UPDATE medlm.idempotency_records
            SET encrypted_response='',invalidated=true
            WHERE user_id=:u AND resource_id=:a"""),
            {"u": self.user_id, "a": analysis_id},
        )
        self.connection.execute(
            text("DELETE FROM medlm.prescriptions WHERE user_id=:u AND analysis_id=:a"),
            {"u": self.user_id, "a": analysis_id},
        )
        self.connection.execute(
            text("DELETE FROM medlm.medicine_analyses WHERE user_id=:u AND id=:a"),
            {"u": self.user_id, "a": analysis_id},
        )

"""Controlled extraction orchestration; adapter execution never holds a transaction."""

from typing import Literal
from uuid import UUID

from medlm_domain.analysis import Contract, ExtractionResult, SyntheticProvenance, Verification
from medlm_domain.extraction import SAFE_ERRORS, ExtractionAdapter, ExtractionMetadata
from pydantic import Field, ValidationError

from medlm_api.analysis_contracts import ExtractionRevision
from medlm_api.analysis_lifecycle_contracts import AnalysisView, LeaseRequest
from medlm_api.analysis_repository import AnalysisRepository
from medlm_api.errors import AppError
from medlm_api.extraction_adapters import DisabledAstraAdapter
from medlm_api.synthetic_fixtures import FixtureInvalid, FixtureRegistry, sha256
from medlm_api.uploads import sql


class ExtractRequest(LeaseRequest):
    lease_token: UUID
    fencing_token: int = Field(strict=True, gt=0)


class SafeFailure(Contract):
    code: Literal["adapter_failure", "invalid_output", "no_observations"]
    message: str


class ExtractResponse(Contract):
    status: AnalysisView
    revision: ExtractionRevision | None
    metadata: ExtractionMetadata | None
    error: SafeFailure | None


class _ReplayMiss(Exception):
    pass


def semantic_observations(result):
    payload = result.model_dump()
    containers = (
        [payload["medicine"]]
        if payload["medicine"]
        else [line["fields"] for line in payload["lines"]]
    )
    for fields in containers:
        for field in fields.values():
            field.pop("confidence")
    return payload


def has_observed_text(result):
    containers = (
        [result.medicine.model_dump()]
        if result.medicine
        else [line.fields.model_dump() for line in result.lines]
    )
    return any(field["raw_text"] is not None for fields in containers for field in fields.values())


def supported_observations(result, expected):
    actual, reference = semantic_observations(result), semantic_observations(expected)
    if result.document_kind == "prescription":
        known = {line["line_id"]: line for line in reference["lines"]}
        pairs = []
        for line in actual["lines"]:
            prior = known.get(line["line_id"])
            if prior is None or prior["ordinal"] != line["ordinal"]:
                return False
            pairs.append((line["fields"], prior["fields"]))
    else:
        pairs = [(actual["medicine"], reference["medicine"])]
    for fields, expected_fields in pairs:
        for name, field in fields.items():
            if field["raw_text"] is None:
                # Abstention must not smuggle invented candidates or locations.
                for key in ("ambiguity_reason", "alternatives", "bounding_box"):
                    if field[key] and field[key] != expected_fields[name][key]:
                        return False
                continue  # Explicit absence is abstention, never a guessed value.
            prior = dict(expected_fields[name])
            for optional in ("normalized_value", "unit"):
                if field[optional] is None:
                    prior[optional] = None
            if field != prior:
                return False
    return True


class SyntheticExtraction:
    def __init__(
        self, lifecycle, registry: FixtureRegistry, adapter: ExtractionAdapter | None = None
    ):
        self.lifecycle, self.registry = lifecycle, registry
        self.adapter = adapter if adapter is not None else DisabledAstraAdapter()

    def current(self, conn, principal, analysis_id, job_id, body, *, version, state):
        a, upload = self.lifecycle.load(conn, principal, analysis_id)
        self.lifecycle.available(a, upload)
        if a["current_job_id"] != job_id:
            raise AppError(409, "stale_job", "This job has been superseded.")
        j = (
            sql(conn, "SELECT * FROM medlm.analysis_jobs WHERE id=:j FOR UPDATE", j=job_id)
            .mappings()
            .one()
        )
        if j["origin_session_id"] != principal.session_id:
            raise AppError(403, "job_session", "Create a new attempt for this session.")
        if version is not None:
            self.lifecycle.version(j["lifecycle_version"], version)
            if j["state"] != state:
                raise AppError(409, "invalid_transition", "Job is not ready for extraction.")
            if (
                j["lease_token"] != body.lease_token
                or j["fencing_token"] != body.fencing_token
                or not j["lease_until"]
                or j["lease_until"] <= self.lifecycle.uploads.clock()
            ):
                raise AppError(409, "stale_lease", "The job lease is no longer current.")
        return a, upload, j

    @staticmethod
    def stage(conn, job_id, body, target, error=None):
        sql(
            conn,
            """SELECT set_config('app.analysis_lease_token',:t,true),
            set_config('app.analysis_fence',:f,true)""",
            t=str(body.lease_token),
            f=str(body.fencing_token),
        )
        sql(
            conn,
            """UPDATE medlm.analysis_jobs SET state=:s, lifecycle_version=lifecycle_version+1,
            safe_error_code=:e,
            lease_token=CASE WHEN :terminal THEN NULL ELSE lease_token END,
            lease_until=CASE WHEN :terminal THEN NULL ELSE lease_until END WHERE id=:j""",
            s=target,
            e=error,
            terminal=target in ("failed", "needs_input"),
            j=job_id,
        )

    def binding(self, conn, principal, upload):
        obj = sql(
            conn,
            """SELECT * FROM medlm.upload_objects WHERE user_id=:u AND upload_id=:id
            AND purged_at IS NULL AND expires_at>clock_timestamp()""",
            u=principal.user_id,
            id=upload.id,
        ).first()
        if obj is None:
            raise AppError(410, "upload_expired", "Image is unavailable.")
        try:
            data = self.lifecycle.uploads.storage.read(principal.user_id, obj.object_key)
            if sha256(data) != obj.checksum_sha256:
                raise FixtureInvalid("Stored checksum mismatch")
            return self.registry.resolve(
                upload.source_checksum_sha256, upload.mime, upload.document_kind, data
            )
        except (FixtureInvalid, AppError):
            raise AppError(422, "fixture_invalid", SAFE_ERRORS["fixture_invalid"]) from None

    def run(self, db, principal, analysis_id, job_id, body, key):
        self.lifecycle.refresh(db, principal, analysis_id)
        operation = f"{analysis_id}:extract:{job_id}"
        payload = body.model_dump(mode="json")
        with self.lifecycle.owned(db, principal) as conn:
            # Replays never restart execution. Concurrent in-flight duplicates get 409.
            self.current(conn, principal, analysis_id, job_id, body, version=None, state=None)

            def miss():
                raise _ReplayMiss()

            try:
                return self.lifecycle.replay(conn, principal, operation, key, payload, miss)
            except _ReplayMiss:
                pass
            a, upload, _ = self.current(
                conn, principal, analysis_id, job_id, body, version=body.job_version, state="queued"
            )
            if not self.adapter.available():
                raise AppError(503, "provider_disabled", SAFE_ERRORS["provider_disabled"])
            request = self.binding(conn, principal, upload)
            metadata = ExtractionMetadata(
                **self.adapter.identity.model_dump(),
                fixture_revision=request.fixture.fixture_revision,
                sanitized_sha256=request.fixture.sanitized_sha256,
            )
            self.stage(conn, job_id, body, "validating")
            self.stage(conn, job_id, body, "extracting")
            parent_version = a["version"]

        # No owner/session/database transaction spans this adapter boundary.
        error, result = None, None
        try:
            raw = self.adapter.extract(request)
        except Exception:
            error = "adapter_failure"
        else:
            try:
                result = ExtractionResult.model_validate(
                    raw.model_dump() if isinstance(raw, ExtractionResult) else raw
                )
                if result.document_kind != request.fixture.document_kind:
                    raise ValueError("Document kind mismatch")
                # Fixture semantic validation: no invented literal/normalized fields.
                expected = self.registry.observations(request)
                if not has_observed_text(result):
                    error = "no_observations"
                elif not supported_observations(result, expected):
                    raise ValueError("Observation differs from registered synthetic text")
            except (ValidationError, ValueError, TypeError):
                error = "invalid_output"
        # Recheck after execution. Stale/expired/cancelled work cannot even publish failure.
        self.lifecycle.refresh(db, principal, analysis_id)
        with self.lifecycle.owned(db, principal) as conn:
            a, upload, _ = self.current(
                conn,
                principal,
                analysis_id,
                job_id,
                body,
                version=body.job_version + 2,
                state="extracting",
            )
            self.lifecycle.version(a["version"], parent_version)
            # Retained object may have been removed or corrupted during execution.
            if self.binding(conn, principal, upload) != request:
                raise AppError(422, "fixture_invalid", SAFE_ERRORS["fixture_invalid"])

            def finish():
                if error:
                    self.stage(
                        conn,
                        job_id,
                        body,
                        "needs_input" if error == "no_observations" else "failed",
                        error,
                    )
                    revision = None
                else:
                    self.stage(conn, job_id, body, "retrieving")
                    self.stage(conn, job_id, body, "validating_output")
                    provenance = SyntheticProvenance(
                        fixture_id=request.fixture.fixture_id,
                        source_sha256=request.fixture.original_sha256,
                    )
                    AnalysisRepository(conn, principal.user_id).publish(
                        analysis_id,
                        job_id,
                        parent_version,
                        result,
                        provenance,
                        lease_token=body.lease_token,
                        fencing_token=body.fencing_token,
                        session_id=principal.session_id,
                        metadata=metadata,
                    )
                    parent, current_upload = self.lifecycle.load(conn, principal, analysis_id)
                    status = self.lifecycle.view(conn, parent, current_upload)
                    revision = ExtractionRevision(
                        analysis_id=analysis_id,
                        revision=status["result_revision"],
                        extraction=result,
                        provenance=provenance,
                        verification=Verification(status="unverified"),
                        review_status="unreviewed",
                    )
                parent, current_upload = self.lifecycle.load(conn, principal, analysis_id)
                response = ExtractResponse(
                    status=self.lifecycle.view(conn, parent, current_upload),
                    revision=revision,
                    metadata=None if error else metadata,
                    error=SafeFailure(code=error, message=SAFE_ERRORS[error]) if error else None,
                )
                return response.model_dump(mode="json"), analysis_id

            return self.lifecycle.replay(conn, principal, operation, key, payload, finish)

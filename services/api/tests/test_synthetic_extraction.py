"""Only registered labelled synthetic images; no live provider/medical facts."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Event
from uuid import uuid4

import httpx
import pytest
from alembic import command
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from medlm_api.analysis_lifecycle import SyntheticAnalyses
from medlm_api.extraction_adapters import (
    AstraBoundaryConfig,
    DeterministicAdapter,
    DisabledAstraAdapter,
)
from medlm_api.main import create_app
from medlm_api.synthetic_extraction import SyntheticExtraction
from medlm_api.synthetic_fixtures import (
    FixtureInvalid,
    FixtureRegistry,
    controlled_catalog,
    controlled_fixture,
)
from medlm_domain.extraction import ExtractionRequest, FixtureDescriptor
from pydantic import SecretStr, ValidationError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_analysis_lifecycle import lease, path, post
from test_auth_sessions import sign_in
from test_upload_runtime import auth_env as _auth_fixture
from test_upload_runtime import complete, initiate
from test_upload_runtime import isolated_database as _db_fixture
from test_upload_runtime import uploads as _uploads_fixture
from test_upload_schema import snapshot

isolated_database = _db_fixture
auth_env = _auth_fixture
uploads = _uploads_fixture
ROOT = Path(__file__).resolve().parents[3]
HEAD = "0008_synthetic_extraction"


@pytest.fixture
def extraction_env(uploads, monkeypatch):
    def no_external_http(*args, **kwargs):
        pytest.fail("External HTTP transport is forbidden in synthetic extraction tests")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", no_external_http)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", no_external_http)
    old, upload, _, _, engine, provider, _ = uploads
    fixtures = controlled_catalog() + (
        controlled_fixture("box", empty=True),
        controlled_fixture("box", ambiguous=True),
        controlled_fixture("prescription", empty=True),
        controlled_fixture("box", mime="image/jpeg"),
        controlled_fixture("box", mime="image/webp"),
    )
    registry = FixtureRegistry(fixtures)
    upload.allowed = registry.original_hashes
    with engine.begin() as c:
        for name in (
            "runtime_grants.sql",
            "synthetic_analysis_grants.sql",
            "synthetic_analysis_lifecycle_grants.sql",
            "synthetic_extraction_grants.sql",
        ):
            c.execute(text((ROOT / "database" / name).read_text()))
    lifecycle = SyntheticAnalyses(upload, SecretStr(Fernet.generate_key().decode()))
    runner = SyntheticExtraction(lifecycle, registry, DeterministicAdapter(registry))
    app = create_app(
        old.app.state.settings,
        provider,
        synthetic_uploads=upload,
        synthetic_analyses=lifecycle,
        synthetic_extraction=runner,
    )
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer synthetic-access"
        yield client, runner, fixtures, engine, provider


def prepared(env, index=3):
    client, _, fixtures, _, _ = env
    item = fixtures[index]
    data, d = item.original_bytes, item.descriptor
    intent = initiate(client, data, document_kind=d.document_kind, content_type=d.mime).json()
    assert (
        client.put(
            "/api/v1" + intent["upload_url"],
            content=data,
            headers={"Content-Type": d.mime, "X-Upload-Ticket": intent["ticket"]},
        ).status_code
        == 204
    )
    assert complete(client, intent, data).status_code == 200
    a = post(
        client,
        "/api/v1/analyses",
        dict(
            upload_id=intent["upload_id"],
            document_kind=d.document_kind,
            content_type=d.mime,
            retain_for_review=True,
            locale="en-IN",
        ),
    ).json()
    a = lease(client, a)
    body = dict(
        job_version=a["job"]["version"],
        lease_token=a["lease_token"],
        fencing_token=a["job"]["fencing_token"],
    )
    return a, body, item


def extract(client, a, body, key=None):
    return post(client, path(a) + f"/jobs/{a['job']['id']}/extract", body, key)


def test_different_encoder_persists_only_registered_canonical_bytes(monkeypatch, request):
    from test_fixture_portability import different_png_encoder

    different_png_encoder(monkeypatch)
    env = request.getfixturevalue("extraction_env")
    client, _, _, engine, _ = env
    a, body, item = prepared(env)
    response = extract(client, a, body)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"]["job"]["state"] == "completed"
    assert result["revision"]["review_status"] == "unreviewed"
    assert result["revision"]["verification"] == {"status": "unverified", "verified_at": None}
    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM medlm.extraction_revisions")).mappings().one()
        assert row["fixture_sha256"] == item.descriptor.original_sha256
        assert row["sanitized_sha256"] == item.descriptor.sanitized_sha256
        obj = conn.execute(text("SELECT * FROM medlm.upload_objects")).mappings().one()
        assert obj["checksum_sha256"] == item.descriptor.sanitized_sha256
        assert conn.scalar(text("SELECT count(*) FROM medlm.medications")) == 0


@pytest.mark.parametrize("kind", ["strip", "bottle", "tube", "box", "prescription"])
def test_registered_fixture_and_determinism(kind, monkeypatch):
    import socket

    monkeypatch.setattr(socket.socket, "connect", lambda *a, **k: pytest.fail("Network call"))
    item = controlled_fixture(kind)
    assert item == controlled_fixture(kind)
    registry = FixtureRegistry((item,))
    d = item.descriptor
    request = registry.resolve(d.original_sha256, d.mime, kind, item.sanitized_bytes)
    adapter = DeterministicAdapter(registry)
    assert adapter.extract(request) == adapter.extract(request) == item.observations
    assert d.original_sha256 != d.sanitized_sha256
    assert d.provenance == "synthetic" and d.purpose == "synthetic_test_not_medical"


@pytest.mark.parametrize(
    "change", ["unknown", "original", "sanitized", "mime", "kind", "revision", "identity"]
)
def test_invalid_binding(change):
    item = controlled_fixture("box")
    registry = FixtureRegistry((item,))
    d = item.descriptor
    with pytest.raises(FixtureInvalid):
        if change in ("revision", "identity"):
            altered = d.model_copy(
                update={"fixture_revision": 2}
                if change == "revision"
                else {"fixture_id": "arbitrary"}
            )
            registry.observations(ExtractionRequest(altered, item.sanitized_bytes))
        else:
            registry.resolve(
                "f" * 64 if change in ("unknown", "original") else d.original_sha256,
                "image/jpeg" if change == "mime" else d.mime,
                "tube" if change == "kind" else d.document_kind,
                b"changed" if change == "sanitized" else item.sanitized_bytes,
            )


def test_fixture_registration_and_contract_reject_forgery():
    item = controlled_fixture("box")
    payload = item.descriptor.model_dump()
    for change in (
        {"provenance": "verified"},
        {"purpose": "medical"},
        {"client_identity": "anything"},
    ):
        with pytest.raises(ValidationError):
            FixtureDescriptor.model_validate(payload | change)
    with pytest.raises(FixtureInvalid):
        FixtureRegistry(
            (replace(item, descriptor=item.descriptor.model_copy(update={"fixture_revision": 2})),)
        )
    with pytest.raises(FixtureInvalid):
        FixtureRegistry((replace(item, original_bytes=b"changed"),))
    with pytest.raises(FixtureInvalid):
        FixtureRegistry((item, item))


def test_disabled_boundary_has_no_transport(monkeypatch):
    import socket

    monkeypatch.setattr(socket.socket, "connect", lambda *a, **k: pytest.fail("Network call"))
    adapter = DisabledAstraAdapter()
    assert not adapter.available()
    with pytest.raises(Exception, match="unavailable"):
        adapter.extract(None)
    with pytest.raises(ValidationError):
        AstraBoundaryConfig(enabled=True)
    with pytest.raises(ValidationError):
        AstraBoundaryConfig(api_key="not-permitted")


@pytest.mark.parametrize("index", [0, 1, 2, 3, 4, 8, 9])
def test_success_binding_revision_and_replay(extraction_env, index):
    client, _, _, engine, _ = extraction_env
    a, body, item = prepared(extraction_env, index)
    key = uuid4()
    response = extract(client, a, body, key)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"]["job"]["state"] == "completed"
    assert result["revision"]["verification"] == {"status": "unverified", "verified_at": None}
    assert result["revision"]["review_status"] == "unreviewed"
    assert extract(client, a, body, key).json() == result
    if index == 4:
        lines = result["revision"]["extraction"]["lines"]
        assert [line["ordinal"] for line in lines] == [0, 1]
        assert len({line["line_id"] for line in lines}) == 2
        assert lines[0]["fields"]["strength"]["raw_text"] == "STRENGTH TOKEN"
        assert lines[0]["fields"]["dose"]["raw_text"] is None
    with engine.connect() as c:
        row = c.execute(text("SELECT * FROM medlm.extraction_revisions")).mappings().one()
        assert row["fixture_sha256"] == item.descriptor.original_sha256
        assert row["sanitized_sha256"] == item.descriptor.sanitized_sha256
        assert row["fixture_revision"] == 1 and row["provider_id"] == "synthetic"
        assert (
            row["model_id"] == "deterministic-v1"
            and row["pipeline_version"] == "synthetic-extraction-v1"
        )
        assert c.scalar(text("SELECT count(*) FROM medlm.medications")) == 0
        assert c.scalar(text("SELECT count(*) FROM medlm.upload_deletion_jobs")) == 0
    with pytest.raises(DBAPIError, match="immutable"):
        with engine.begin() as c:
            c.execute(text("UPDATE medlm.extraction_revisions SET fixture_revision=2"))


@pytest.mark.parametrize(
    "mode", ["disabled", "unknown", "stored_bytes", "original_hash", "mime", "kind"]
)
def test_preflight_rejects_without_state_change(extraction_env, mode):
    client, runner, _, _, _ = extraction_env
    a, body, _ = prepared(extraction_env)
    if mode == "disabled":
        runner.adapter = DisabledAstraAdapter()
    elif mode == "unknown":
        runner.registry = FixtureRegistry(())
    elif mode == "stored_bytes":
        runner.lifecycle.uploads.storage.read = lambda *args: b"changed"
    else:
        original_resolve = runner.registry.resolve

        def altered(source, mime, kind, data):
            return original_resolve(
                "f" * 64 if mode == "original_hash" else source,
                "image/jpeg" if mode == "mime" else mime,
                "tube" if mode == "kind" else kind,
                data,
            )

        runner.registry.resolve = altered
    response = extract(client, a, body)
    assert response.status_code in (422, 503), response.text
    status = client.get(path(a)).json()
    assert status["job"]["state"] == "queued" and status["job"]["version"] == body["job_version"]
    assert status["result_revision"] is None


@pytest.mark.parametrize(
    "mode,code",
    [
        ("raise", "adapter_failure"),
        ("malformed", "invalid_output"),
        ("invented", "invalid_output"),
        ("absent_alternatives", "invalid_output"),
    ],
)
def test_adapter_failure_is_safe_and_terminal(extraction_env, mode, code):
    client, runner, _, engine, _ = extraction_env
    a, body, _ = prepared(extraction_env)

    def fail(request):
        if mode == "raise":
            raise RuntimeError("private adapter internals must not escape")
        if mode == "malformed":
            return {"verified_at": "anything"}
        result = runner.registry.observations(request).model_dump()
        if mode == "absent_alternatives":
            result["medicine"]["strength"]["alternatives"] = ("invented candidate",)
            result["medicine"]["strength"]["ambiguity_reason"] = "invented ambiguity"
        else:
            result["medicine"]["strength"]["raw_text"] = "invented"
        return result

    runner.adapter.extract = fail
    response = extract(client, a, body)
    assert response.status_code == 200, response.text
    assert response.json()["status"]["job"]["state"] == "failed"
    assert response.json()["error"]["code"] == code
    assert "private adapter" not in response.text
    with engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM medlm.extraction_revisions")) == 0
        assert c.scalar(text("SELECT safe_error_code FROM medlm.analysis_jobs")) == code


@pytest.mark.parametrize("index", [5, 7])
def test_empty_observations_need_input(extraction_env, index):
    client, _, _, engine, _ = extraction_env
    a, body, _ = prepared(extraction_env, index)
    response = extract(client, a, body)
    assert response.status_code == 200, response.text
    assert response.json()["status"]["job"]["state"] == "needs_input"
    assert response.json()["revision"] is None
    with engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM medlm.extraction_revisions")) == 0


def test_empty_adapter_output_for_nonempty_fixture_needs_input(extraction_env):
    client, runner, _, _, _ = extraction_env
    a, body, _ = prepared(extraction_env)
    runner.adapter.extract = lambda request: controlled_fixture("box", empty=True).observations
    response = extract(client, a, body)
    assert response.status_code == 200
    assert response.json()["status"]["job"]["state"] == "needs_input"
    assert response.json()["revision"] is None


def test_partial_prescription_output_preserves_omissions(extraction_env):
    client, runner, _, _, _ = extraction_env
    a, body, _ = prepared(extraction_env, 4)
    original = runner.adapter.extract

    def partial(request):
        payload = original(request).model_dump()
        payload["lines"] = payload["lines"][:1]
        payload["lines"][0]["fields"]["strength"] = payload["lines"][0]["fields"]["dose"]
        return payload

    runner.adapter.extract = partial
    response = extract(client, a, body)
    assert response.status_code == 200, response.text
    revision = response.json()["revision"]
    assert len(revision["extraction"]["lines"]) == 1
    assert revision["extraction"]["lines"][0]["fields"]["strength"]["raw_text"] is None
    assert revision["review_status"] == "unreviewed"


def test_ambiguity_nulls_and_confidence_not_acceptance(extraction_env):
    client, runner, _, _, _ = extraction_env
    a, body, item = prepared(extraction_env, 6)
    original = runner.adapter.extract

    def confidence(request):
        result = original(request).model_dump()
        result["medicine"]["medicine"]["confidence"] = dict(
            source="fixture", score=0.0, calibration="uncalibrated"
        )
        return result

    runner.adapter.extract = confidence
    response = extract(client, a, body)
    assert response.status_code == 200, response.text
    revision = response.json()["revision"]
    assert (
        revision["review_status"] == "unreviewed"
        and revision["verification"]["status"] == "unverified"
    )
    fields = revision["extraction"]["medicine"]
    assert (
        fields["medicine"]["ambiguity_reason"]
        == item.observations.medicine.medicine.ambiguity_reason
    )
    assert fields["strength"]["raw_text"] is None


def test_retry_creates_new_immutable_revision(extraction_env):
    client, _, _, engine, _ = extraction_env
    a, body, _ = prepared(extraction_env)
    first = extract(client, a, body).json()
    b = post(client, path(a) + "/jobs", dict(version=first["status"]["version"])).json()
    b = lease(client, b)
    response = extract(
        client,
        b,
        dict(
            job_version=b["job"]["version"],
            lease_token=b["lease_token"],
            fencing_token=b["job"]["fencing_token"],
        ),
    )
    assert response.status_code == 200, response.text
    assert response.json()["revision"]["revision"] == 2
    assert extract(client, a, body).status_code == 409
    with engine.connect() as c:
        assert c.execute(
            text("SELECT revision FROM medlm.extraction_revisions ORDER BY revision")
        ).scalars().all() == [1, 2]


def test_duplicate_prescription_output_fails(extraction_env):
    client, runner, _, _, _ = extraction_env
    a, body, _ = prepared(extraction_env, 4)
    original = runner.adapter.extract

    def duplicate(request):
        result = original(request).model_dump()
        result["lines"][1]["ordinal"] = result["lines"][0]["ordinal"]
        return result

    runner.adapter.extract = duplicate
    response = extract(client, a, body)
    assert response.status_code == 200
    assert response.json()["error"]["code"] == "invalid_output"
    assert response.json()["revision"] is None


def test_concurrent_duplicate_execution_has_one_adapter_call(extraction_env):
    client, runner, _, engine, _ = extraction_env
    a, body, _ = prepared(extraction_env)
    entered, resume = Event(), Event()
    original = runner.adapter.extract
    calls = []

    def blocked(request):
        calls.append(request)
        entered.set()
        assert resume.wait(10)
        return original(request)

    runner.adapter.extract = blocked
    key = uuid4()
    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(extract, client, a, body, key)
        assert entered.wait(5)
        assert extract(client, a, body, key).status_code == 409
        resume.set()
        result = future.result()
    assert result.status_code == 200
    assert extract(client, a, body, key).json() == result.json()
    assert len(calls) == 1
    with engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM medlm.extraction_revisions")) == 1


@pytest.mark.parametrize("race", ["retry", "cancel", "logout", "expiry", "fence"])
def test_execution_race_cannot_publish(extraction_env, race):
    client, runner, _, engine, _ = extraction_env
    if race == "expiry":
        runner.lifecycle.uploads.ttl = 3
    if race == "fence":
        runner.lifecycle.lease_seconds = 1
    a, body, _ = prepared(extraction_env)
    entered, resume = Event(), Event()
    original = runner.adapter.extract

    def blocked(request):
        entered.set()
        assert resume.wait(15)
        return original(request)

    runner.adapter.extract = blocked
    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(extract, client, a, body)
        assert entered.wait(10)
        # A separate transaction can operate while the adapter is running.
        if race == "retry":
            assert post(client, path(a) + "/jobs", dict(version=a["version"])).status_code == 201
        elif race == "cancel":
            assert post(client, path(a) + "/cancel", dict(version=a["version"])).status_code == 200
        elif race == "logout":
            assert client.delete("/api/v1/auth/session").status_code == 204
        else:
            with engine.connect() as c:
                c.execute(
                    text("SELECT pg_sleep(:seconds)"), {"seconds": 3.1 if race == "expiry" else 1.1}
                )
            if race == "fence":
                status = client.get(path(a)).json()
                lease(client, status)
        resume.set()
        assert future.result().status_code in (401, 409, 410)
    with engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM medlm.extraction_revisions")) == 0
        assert c.scalar(text("SELECT count(*) FROM medlm.analysis_jobs WHERE state='failed'")) == 0


def test_security_metadata_and_fencing(extraction_env):
    client, _, _, engine, provider = extraction_env
    a, body, _ = prepared(extraction_env)
    for extra in (
        "fixture_id",
        "fixture_revision",
        "provider_id",
        "model_id",
        "observations",
        "provenance",
        "checksum",
    ):
        assert extract(client, a, body | {extra: "arbitrary"}).status_code == 422
    assert extract(client, a, body | {"fencing_token": 999}).status_code == 409
    owner = provider.user
    provider.user = uuid4()
    assert extract(client, a, body).status_code == 404
    with engine.begin() as c:
        c.execute(text("SET LOCAL ROLE medlm_runtime"))
        c.execute(text("SELECT set_config('app.user_id',:u,true)"), {"u": str(provider.user)})
        assert c.scalar(text("SELECT count(*) FROM medlm.analysis_jobs")) == 0
    provider.user = owner
    client.headers.pop("Authorization")
    assert extract(client, a, body).status_code == 401
    cookie, csrf, _ = sign_in(client.app)
    client.cookies.set("medlm_session", cookie)
    route = path(a) + f"/jobs/{a['job']['id']}/extract"
    headers = {"Origin": client.app.state.settings.cors_origins[0], "Idempotency-Key": str(uuid4())}
    assert client.post(route, json=body, headers=headers).status_code == 403
    assert (
        client.post(route, json=body, headers=headers | {"X-CSRF-Token": csrf}).status_code == 200
    )


def test_migration_roundtrip(isolated_database):
    engine, cfg = isolated_database
    command.upgrade(cfg, "0007_analysis_lifecycle")
    with engine.connect() as c:
        before = snapshot(c)
        guard = c.scalar(
            text("SELECT pg_get_functiondef('medlm.guard_analysis_child()'::regprocedure)")
        )
    command.upgrade(cfg, HEAD)  # Preserve the Chunk 4 migration checkpoint.
    with engine.connect() as c:
        assert c.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
    command.downgrade(cfg, "0007_analysis_lifecycle")
    with engine.connect() as c:
        assert snapshot(c) == before
        assert (
            c.scalar(
                text("SELECT pg_get_functiondef('medlm.guard_analysis_child()'::regprocedure)")
            )
            == guard
        )
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


def test_populated_downgrade_and_security(extraction_env, isolated_database):
    client, _, _, engine, _ = extraction_env
    a, body, _ = prepared(extraction_env)
    assert extract(client, a, body).status_code == 200
    with pytest.raises(DBAPIError, match="export/erasure"):
        command.downgrade(isolated_database[1], "0007_analysis_lifecycle")
    with engine.connect() as c:
        assert not any(
            c.execute(
                text(
                    "SELECT rolsuper,rolcreatedb,rolcreaterole,rolbypassrls FROM pg_roles WHERE rolname='medlm_runtime'"
                )
            ).one()
        )
        assert c.scalar(
            text(
                "SELECT bool_and(relrowsecurity AND relforcerowsecurity) FROM pg_class WHERE oid IN ('medlm.analysis_jobs'::regclass,'medlm.extraction_revisions'::regclass)"
            )
        )
        assert not c.scalar(
            text(
                "SELECT count(*) FROM pg_proc WHERE pronamespace='medlm'::regnamespace AND prosecdef"
            )
        )
        assert not c.scalar(
            text(
                "SELECT has_column_privilege('medlm_runtime','medlm.extraction_revisions','provider_id','UPDATE')"
            )
        )


def test_legacy_lifecycle_survives_metadata_roundtrip(extraction_env, isolated_database):
    client, _, _, engine, _ = extraction_env
    a, _, _ = prepared(extraction_env)
    with engine.connect() as c:
        parent = c.execute(text("SELECT to_jsonb(a) FROM medlm.medicine_analyses a")).scalar_one()
        job = c.execute(
            text("SELECT to_jsonb(j)-'safe_error_code' FROM medlm.analysis_jobs j")
        ).scalar_one()
    command.downgrade(isolated_database[1], "0007_analysis_lifecycle")
    with engine.connect() as c:
        assert (
            c.execute(text("SELECT to_jsonb(a) FROM medlm.medicine_analyses a")).scalar_one()
            == parent
        )
        assert c.execute(text("SELECT to_jsonb(j) FROM medlm.analysis_jobs j")).scalar_one() == job
    command.upgrade(isolated_database[1], HEAD)
    assert client.get(path(a)).json()["job"]["state"] == "queued"

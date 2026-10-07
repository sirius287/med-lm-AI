"""No extraction provider: only existing generated image and persistence test data."""

import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from medlm_api.analysis_lifecycle import SyntheticAnalyses
from medlm_api.analysis_repository import AnalysisConflict, AnalysisRepository
from medlm_api.main import create_app
from medlm_domain.analysis import SyntheticProvenance
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_analysis_schema import extraction, snapshot, workflow
from test_auth_sessions import sign_in
from test_upload_runtime import accepted, complete, fixture_image, initiate, transfer
from test_upload_runtime import auth_env as _auth_fixture
from test_upload_runtime import isolated_database as _database_fixture
from test_upload_runtime import uploads as _upload_fixture

isolated_database = _database_fixture
auth_env = _auth_fixture
uploads = _upload_fixture
ROOT = Path(__file__).resolve().parents[3]
HEAD = "0007_analysis_lifecycle"


@pytest.fixture
def lifecycle(uploads):
    _, upload_service, worker, data, engine, provider, _ = uploads
    with engine.begin() as conn:
        for name in (
            "runtime_grants.sql",
            "synthetic_analysis_grants.sql",
            "synthetic_analysis_lifecycle_grants.sql",
        ):
            conn.execute(text((ROOT / "database" / name).read_text()))
    service = SyntheticAnalyses(upload_service, SecretStr(Fernet.generate_key().decode()))
    settings = uploads[0].app.state.settings
    app = create_app(
        settings, provider, synthetic_uploads=upload_service, synthetic_analyses=service
    )
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer synthetic-access"
        yield client, service, worker, data, engine, provider


def post(client, path, body, key=None):
    return client.post(path, json=body, headers={"Idempotency-Key": str(key or uuid4())})


def create(client, data, kind="box"):
    intent = initiate(client, data, document_kind=kind).json()
    assert transfer(client, intent, data).status_code == 204
    assert complete(client, intent, data).status_code == 200
    body = dict(
        upload_id=intent["upload_id"],
        document_kind=kind,
        content_type="image/png",
        retain_for_review=True,
        locale="en-IN",
    )
    key = uuid4()
    response = post(client, "/api/v1/analyses", body, key)
    assert response.status_code == 201, response.text
    return response.json(), body, key


def path(a):
    return f"/api/v1/analyses/{a['id']}"


def lease(client, a):
    response = post(
        client, path(a) + f"/jobs/{a['job']['id']}/lease", dict(job_version=a["job"]["version"])
    )
    assert response.status_code == 200, response.text
    return response.json()


def advance(client, a, token, target, **changes):
    body = dict(
        job_version=a["job"]["version"],
        lease_token=token,
        fencing_token=a["job"]["fencing_token"],
        target=target,
    )
    body.update(changes)
    return post(client, path(a) + f"/jobs/{a['job']['id']}/transitions", body)


def ready(client, a):
    a = lease(client, a)
    token = a["lease_token"]
    for state in ("validating", "extracting", "retrieving", "validating_output"):
        response = advance(client, a, token, state)
        assert response.status_code == 200, response.text
        a = response.json()
    return a, token


def publish_for_test(client, service, provider, a, token):
    principal = provider.verify_local("synthetic-access")
    with service.owned(client.app.state.database, principal) as conn:
        return AnalysisRepository(conn, principal.user_id).publish(
            UUID(a["id"]),
            UUID(a["job"]["id"]),
            a["version"],
            extraction(),
            SyntheticProvenance(fixture_id="lifecycle-test", source_sha256="a" * 64),
            lease_token=UUID(token),
            fencing_token=a["job"]["fencing_token"],
            session_id=principal.session_id,
        )


@pytest.mark.parametrize("kind", ["strip", "bottle", "tube", "box", "prescription"])
def test_create_replay_and_retry_preserve_parent_deadline(lifecycle, kind):
    client, _, _, data, engine, _ = lifecycle
    a, body, key = create(client, data, kind)
    assert a["job"]["state"] == "queued" and a["job"]["attempt"] == 1
    assert post(client, "/api/v1/analyses", body, key).json() == a
    assert post(client, "/api/v1/analyses", body).status_code == 409
    assert post(client, "/api/v1/analyses", body | {"locale": "hi-IN"}, key).status_code == 409
    response = post(client, path(a) + "/jobs", dict(version=a["version"]))
    assert response.status_code == 201, response.text
    b = response.json()
    assert b["id"] == a["id"] and b["job"]["id"] != a["job"]["id"]
    assert b["job"]["attempt"] == 2 and b["expires_at"] == a["expires_at"]
    assert (
        post(client, path(a) + f"/jobs/{a['job']['id']}/lease", dict(job_version=1)).status_code
        == 409
    )
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM medlm.medicine_analyses")) == 1
        assert conn.scalar(text("SELECT count(*) FROM medlm.analysis_uploads")) == 1
        assert (
            conn.scalar(text("SELECT state FROM medlm.analysis_jobs WHERE attempt=1")) == "queued"
        )


@pytest.mark.parametrize(
    "change",
    [
        {"content_type": "application/pdf"},
        {"content_type": "image/heic"},
        {"document_kind": "pdf"},
        {"retain_for_review": False},
        {"retain_for_review": None},
        {"external_url": "https://example.invalid/image"},
        {"observations": {}},
    ],
)
def test_invalid_analysis_input(lifecycle, change):
    client, _, _, data, _, _ = lifecycle
    a, body, _ = create(client, data)
    assert post(client, "/api/v1/analyses", body | change).status_code == 422


def test_upload_retention_and_declared_kind_match(lifecycle):
    client, _, _, data, _, _ = lifecycle
    intent, _, _ = accepted(client, data, review=False)
    body = dict(
        upload_id=intent["upload_id"],
        document_kind="box",
        content_type="image/png",
        retain_for_review=True,
        locale="en-IN",
    )
    assert post(client, "/api/v1/analyses", body).status_code == 410
    intent, _, _ = accepted(client, data)
    body["upload_id"] = intent["upload_id"]
    assert post(client, "/api/v1/analyses", body | {"document_kind": "tube"}).status_code == 422
    assert (
        post(client, "/api/v1/analyses", body | {"content_type": "image/jpeg"}).status_code == 422
    )


def test_authentication_and_owner_isolation(lifecycle):
    client, _, _, data, engine, provider = lifecycle
    a, body, _ = create(client, data)
    owner = provider.user
    provider.user = uuid4()
    assert post(client, "/api/v1/analyses", body).status_code == 404
    assert client.get(path(a)).status_code == 404
    assert post(client, path(a) + "/cancel", dict(version=a["version"])).status_code == 404
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE medlm_runtime"))
        conn.execute(text("SELECT set_config('app.user_id',:u,true)"), {"u": str(provider.user)})
        assert conn.scalar(text("SELECT count(*) FROM medlm.analysis_jobs")) == 0
    provider.user = owner
    client.headers.pop("Authorization")
    assert post(client, "/api/v1/analyses", body).status_code == 401
    assert client.get(path(a)).status_code == 401
    for suffix, payload in (
        ("/cancel", dict(version=2)),
        ("/jobs", dict(version=2)),
        (f"/jobs/{a['job']['id']}/lease", dict(job_version=1)),
        (
            f"/jobs/{a['job']['id']}/transitions",
            dict(job_version=1, lease_token=str(uuid4()), fencing_token=1, target="validating"),
        ),
    ):
        assert post(client, path(a) + suffix, payload).status_code == 401


def test_completion_only_through_test_persistence_retains_review(lifecycle):
    client, service, _, data, engine, provider = lifecycle
    a, body, _ = create(client, data)
    a, token = ready(client, a)
    assert advance(client, a, token, "completed").status_code == 422
    publish_for_test(client, service, provider, a, token)
    result = client.get(path(a)).json()
    assert result["job"]["state"] == "completed" and result["result_revision"] == 1
    assert result["expires_at"] == a["expires_at"]
    assert client.get(f"/api/v1/uploads/{body['upload_id']}/preview").status_code == 200
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM medlm.upload_deletion_jobs")) == 0
        assert (
            conn.scalar(text("SELECT verification FROM medlm.extraction_revisions")) == "unverified"
        )
    assert (
        post(
            client,
            path(a) + f"/jobs/{a['job']['id']}/lease",
            dict(job_version=result["job"]["version"]),
        ).status_code
        == 409
    )
    b = post(client, path(a) + "/jobs", dict(version=result["version"])).json()
    b, second_token = ready(client, b)
    with pytest.raises(AnalysisConflict):
        publish_for_test(client, service, provider, a, token)
    publish_for_test(client, service, provider, b, second_token)
    with engine.connect() as conn:
        assert conn.execute(
            text("SELECT revision FROM medlm.extraction_revisions ORDER BY revision")
        ).scalars().all() == [1, 2]


@pytest.mark.parametrize("target", ["extracting", "retrieving", "validating_output"])
def test_stage_skipping_rejected(lifecycle, target):
    client, _, _, data, _, _ = lifecycle
    a, _, _ = create(client, data)
    a = lease(client, a)
    assert advance(client, a, a["lease_token"], target).status_code == 409


def test_same_backwards_and_stale_fence_rejected(lifecycle):
    client, _, _, data, _, _ = lifecycle
    a, _, _ = create(client, data)
    a = lease(client, a)
    token = a["lease_token"]
    assert advance(client, a, str(uuid4()), "validating").status_code == 409
    assert advance(client, a, token, "validating", fencing_token=9).status_code == 409
    a = advance(client, a, token, "validating").json()
    assert advance(client, a, token, "validating").status_code == 409
    a = advance(client, a, token, "extracting").json()
    assert advance(client, a, token, "validating").status_code == 409


@pytest.mark.parametrize("outcome", ["failed", "needs_input", "cancelled"])
def test_terminal_outcomes_from_queued(lifecycle, outcome):
    client, _, _, data, _, _ = lifecycle
    a, _, _ = create(client, data)
    a = lease(client, a)
    token = a["lease_token"]
    response = advance(client, a, token, outcome)
    assert response.status_code == 200, response.text
    ended = response.json()
    assert ended["job"]["state"] == outcome
    assert advance(client, ended, token, "validating").status_code in (409, 410)
    if outcome != "cancelled":
        assert post(client, path(a) + "/jobs", dict(version=ended["version"])).status_code == 201


def test_cancel_replay_queues_real_deletion_and_receipt(lifecycle):
    client, _, worker, data, engine, _ = lifecycle
    a, body, _ = create(client, data)
    key = uuid4()
    request = dict(version=a["version"])
    result = post(client, path(a) + "/cancel", request, key)
    assert result.status_code == 200, result.text
    assert result.json()["availability"] == "cancelled"
    assert post(client, path(a) + "/cancel", request, key).json() == result.json()
    assert (
        post(client, path(a) + "/jobs", dict(version=result.json()["version"])).status_code == 410
    )
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM medlm.upload_deletion_jobs")) == 1
    assert worker.run("deletion_worker")["outcome"] == "ok"
    assert client.get(f"/api/v1/uploads/{body['upload_id']}/receipts").json()["receipts"]


def test_expiry_persists_marker_fences_publication_and_schedules_deletion(lifecycle):
    client, service, worker, data, engine, provider = lifecycle
    service.uploads.ttl = 4
    a, body, _ = create(client, data)
    a, token = ready(client, a)
    with engine.connect() as conn:
        conn.execute(text("SELECT pg_sleep(4.1)"))
    with pytest.raises(DBAPIError):
        publish_for_test(client, service, provider, a, token)
    expired = client.get(path(a)).json()
    assert expired["availability"] == "expired" and expired["expired_at"]
    assert expired["job"]["state"] == "validating_output"
    assert expired["expires_at"] == a["expires_at"]
    assert post(client, path(a) + "/jobs", dict(version=expired["version"])).status_code == 410
    assert advance(client, a, token, "failed").status_code == 410
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM medlm.extraction_revisions")) == 0
        assert conn.scalar(text("SELECT reason FROM medlm.upload_deletion_jobs")) == "expiry"
    assert worker.run("independent_sweep")["outcome"] == "ok"
    assert client.get(f"/api/v1/uploads/{body['upload_id']}/preview").status_code == 410


def test_expired_lease_reacquisition_changes_fence(lifecycle):
    client, service, _, data, engine, _ = lifecycle
    service.lease_seconds = 1
    a, _, _ = create(client, data)
    first = lease(client, a)
    with engine.connect() as conn:
        conn.execute(text("SELECT pg_sleep(1.1)"))
    second = lease(client, first)
    assert second["job"]["fencing_token"] == 2
    assert second["lease_token"] != first["lease_token"]
    assert advance(client, second, first["lease_token"], "validating").status_code == 409
    assert advance(client, second, second["lease_token"], "validating").status_code == 200


def test_concurrent_lease_has_one_winner(lifecycle):
    client, _, _, data, _, _ = lifecycle
    a, _, _ = create(client, data)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: (
                    post(
                        client, path(a) + f"/jobs/{a['job']['id']}/lease", dict(job_version=1)
                    ).status_code
                ),
                range(2),
            )
        )
    assert sorted(results) == [200, 409]


@pytest.mark.parametrize("reason", ["logout", "disabled", "new_session"])
def test_session_account_boundaries(lifecycle, reason):
    client, _, _, data, engine, provider = lifecycle
    a, _, _ = create(client, data)
    a = lease(client, a)
    if reason == "logout":
        assert client.delete("/api/v1/auth/session").status_code == 204
    elif reason == "disabled":
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE medlm.users SET disabled_at=now() WHERE id=:u"), {"u": provider.user}
            )
    else:
        provider.sid = uuid4()
    assert advance(client, a, a["lease_token"], "validating").status_code in (401, 403)


def test_migration_roundtrip_and_legacy_history(isolated_database):
    engine, cfg = isolated_database
    command.upgrade(cfg, "0006_analysis_foundation")
    u = uuid4()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO medlm.users(id) VALUES (:u)"), {"u": u})
        a, _, _ = workflow(conn, u)
        before = snapshot(conn)
        guard = conn.scalar(
            text("SELECT pg_get_functiondef('medlm.guard_analysis_child()'::regprocedure)")
        )
    command.upgrade(cfg, HEAD)
    with engine.connect() as conn:
        assert (
            conn.scalar(
                text("SELECT expires_at FROM medlm.medicine_analyses WHERE id=:a"), {"a": a}
            )
            is None
        )
    command.downgrade(cfg, "0006_analysis_foundation")
    with engine.connect() as conn:
        assert snapshot(conn) == before
        assert (
            conn.scalar(
                text("SELECT pg_get_functiondef('medlm.guard_analysis_child()'::regprocedure)")
            )
            == guard
        )
        assert conn.scalar(text("SELECT count(*) FROM medlm.extraction_revisions")) == 1


def test_fresh_head_and_empty_roundtrip(isolated_database):
    engine, cfg = isolated_database
    command.upgrade(cfg, "0006_analysis_foundation")
    with engine.connect() as conn:
        before = snapshot(conn)
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
    command.downgrade(cfg, "0006_analysis_foundation")
    with engine.connect() as conn:
        assert snapshot(conn) == before
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == HEAD


def test_transition_replay_does_not_advance_twice(lifecycle):
    client, _, _, data, _, _ = lifecycle
    a, _, _ = create(client, data)
    a = lease(client, a)
    request = dict(
        job_version=a["job"]["version"],
        lease_token=a["lease_token"],
        fencing_token=a["job"]["fencing_token"],
        target="validating",
    )
    route = path(a) + f"/jobs/{a['job']['id']}/transitions"
    key = uuid4()
    result = post(client, route, request, key)
    assert result.status_code == 200
    assert post(client, route, request, key).json() == result.json()
    assert post(client, route, request).status_code == 409
    assert client.get(path(a)).json()["job"]["version"] == a["job"]["version"] + 1


@pytest.mark.parametrize("format,mime", [("JPEG", "image/jpeg"), ("WEBP", "image/webp")])
def test_other_approved_image_formats(lifecycle, format, mime):
    client, service, _, _, _, _ = lifecycle
    data = fixture_image(format)
    service.uploads.allowed = frozenset([hashlib.sha256(data).hexdigest()])
    intent = initiate(client, data, content_type=mime).json()
    result = client.put(
        "/api/v1" + intent["upload_url"],
        content=data,
        headers={"Content-Type": mime, "X-Upload-Ticket": intent["ticket"]},
    )
    assert result.status_code == 204, result.text
    assert complete(client, intent, data).status_code == 200
    result = post(
        client,
        "/api/v1/analyses",
        dict(
            upload_id=intent["upload_id"],
            document_kind="box",
            content_type=mime,
            retain_for_review=True,
            locale="en-IN",
        ),
    )
    assert result.status_code == 201, result.text


def test_cookie_mutation_requires_csrf(lifecycle):
    client, _, _, data, _, _ = lifecycle
    a, _, _ = create(client, data)
    cookie, csrf, _ = sign_in(client.app)
    client.headers.pop("Authorization")
    client.cookies.set("medlm_session", cookie)
    route = path(a) + "/cancel"
    headers = {"Origin": client.app.state.settings.cors_origins[0], "Idempotency-Key": str(uuid4())}
    body = dict(version=a["version"])
    assert client.post(route, json=body, headers=headers).status_code == 403
    assert client.get(path(a)).json()["availability"] == "available"
    assert (
        client.post(route, json=body, headers=headers | {"X-CSRF-Token": csrf}).status_code == 200
    )


def test_deadline_and_unleased_publication_cannot_be_bypassed(lifecycle):
    client, service, _, data, engine, provider = lifecycle
    a, _, _ = create(client, data)
    with pytest.raises(DBAPIError, match="deadline is immutable"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE medlm.medicine_analyses SET expires_at=expires_at+interval '1 second' WHERE id=:a"
                ),
                {"a": a["id"]},
            )
    a, token = ready(client, a)
    with pytest.raises(DBAPIError, match="Stale analysis lease"):
        publish_for_test(client, service, provider, a, str(uuid4()))
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM medlm.extraction_revisions")) == 0
    publish_for_test(client, service, provider, a, token)


def test_populated_rollback_and_grants(lifecycle, isolated_database):
    client, _, _, data, engine, _ = lifecycle
    create(client, data)
    with pytest.raises(DBAPIError, match="Lifecycle data exists"):
        command.downgrade(isolated_database[1], "0006_analysis_foundation")
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
        assert not any(
            conn.execute(
                text(
                    "SELECT rolsuper,rolcreatedb,rolcreaterole,rolbypassrls FROM pg_roles WHERE rolname='medlm_runtime'"
                )
            ).one()
        )
        assert conn.scalar(
            text(
                "SELECT bool_and(relrowsecurity AND relforcerowsecurity) FROM pg_class WHERE oid IN ('medlm.medicine_analyses'::regclass,'medlm.analysis_jobs'::regclass)"
            )
        )
        assert not conn.scalar(
            text("SELECT has_table_privilege('medlm_upload_worker','medlm.analysis_jobs','SELECT')")
        )
        assert not conn.scalar(
            text(
                "SELECT count(*) FROM pg_proc WHERE pronamespace='medlm'::regnamespace AND prosecdef"
            )
        )


def test_no_result_endpoint_and_default_app_disabled(lifecycle):
    client, service, _, _, _, provider = lifecycle
    paths = client.app.openapi()["paths"]
    assert not any("publish" in p or "extract" in p for p in paths)
    app = create_app(client.app.state.settings, provider)
    try:
        assert not any(p.startswith("/api/v1/analyses") for p in app.openapi()["paths"])
    finally:
        app.state.database.close()
    with pytest.raises(ValueError):
        create_app(client.app.state.settings, provider, synthetic_analyses=service)

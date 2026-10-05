import hashlib
import io
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from medlm_api.config import Settings
from medlm_api.database import Database
from medlm_api.errors import AppError
from medlm_api.main import create_app
from medlm_api.upload_maintenance import UploadMaintenance
from medlm_api.upload_storage import LocalSyntheticStorage
from medlm_api.uploads import SyntheticUploads, sql, utcnow
from PIL import Image
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_auth_sessions import auth_env as _auth_fixture
from test_upload_schema import isolated_database as _database_fixture

isolated_database = _database_fixture
auth_env = _auth_fixture
ROOT = Path(__file__).resolve().parents[3]


def fixture_image(format="PNG"):
    output = io.BytesIO()
    Image.new("RGB", (8, 8), "blue").save(output, format=format)
    return output.getvalue()


@pytest.fixture
def uploads(auth_env, tmp_path):
    engine, settings, provider, base_app = auth_env
    with engine.begin() as conn:
        conn.execute(
            text("""DO $$ BEGIN
            IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='medlm_upload_worker') THEN
                CREATE ROLE medlm_upload_worker NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
            END IF; END $$""")
        )
        conn.execute(text((ROOT / "database/synthetic_upload_grants.sql").read_text()))
    worker_db = Database(
        Settings(
            _env_file=None,
            database_url=engine.url.update_query_dict(
                {"options": "-c role=medlm_upload_worker"}
            ).render_as_string(hide_password=False),
        )
    )
    data = fixture_image()
    key = Fernet.generate_key()
    storage = LocalSyntheticStorage(tmp_path / "objects", key)
    service = SyntheticUploads(storage, frozenset([hashlib.sha256(data).hexdigest()]))
    maintenance = UploadMaintenance(worker_db, storage)
    try:
        for kind in ("independent_sweep", "deletion_worker", "reconciliation"):
            assert maintenance.run(kind)["outcome"] == "ok"
    except BaseException:
        worker_db.close()
        raise
    app = create_app(settings, provider, synthetic_uploads=service)
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer synthetic-access"
        yield client, service, maintenance, data, engine, provider, key
    worker_db.close()


def initiate(client, data, review=True, key=None, **overrides):
    body = dict(
        content_type="image/png",
        byte_size=len(data),
        document_kind="box",
        consent_version="synthetic-v1",
        retain_for_review=review,
        checksum_sha256=hashlib.sha256(data).hexdigest(),
    )
    body.update(overrides)
    return client.post(
        "/api/v1/uploads", json=body, headers={"Idempotency-Key": str(key or uuid4())}
    )


def transfer(client, intent, data):
    return client.put(
        "/api/v1" + intent["upload_url"],
        content=data,
        headers={"Content-Type": "image/png", "X-Upload-Ticket": intent["ticket"]},
    )


def complete(client, intent, data):
    path = f"/api/v1/uploads/{intent['upload_id']}"
    version = client.get(path).json()["version"]
    return client.post(
        path + "/complete",
        json={"checksum_sha256": hashlib.sha256(data).hexdigest()},
        headers={"If-Match": f'"{version}"', "Idempotency-Key": str(uuid4())},
    )


def accepted(client, data, review=True):
    response = initiate(client, data, review)
    assert response.status_code == 201, response.text
    intent = response.json()
    assert transfer(client, intent, data).status_code == 204
    response = complete(client, intent, data)
    assert response.status_code == 200, response.text
    return intent, response.json(), f"/api/v1/uploads/{intent['upload_id']}"


def test_durable_roundtrip_encrypted_preview_deletion_receipts(uploads):
    client, service, worker, data, engine, provider, key = uploads
    intent, current, path = accepted(client, data)
    stored_key = service.storage.keys()[0]
    snapshot = (service.storage.root / str(stored_key)).read_bytes()
    assert data not in (service.storage.root / str(stored_key)).read_bytes()
    # Reopen the adapter: no in-memory object catalog or plaintext temporary files.
    reopened = LocalSyntheticStorage(service.storage.root, key)
    assert reopened.read(provider.user, stored_key) == client.get(path + "/preview").content
    with pytest.raises(AppError):
        reopened.read(uuid4(), stored_key)
    preview = client.get(path + "/preview")
    assert preview.headers["cache-control"] == "no-store"
    assert preview.headers["content-type"] == "image/png"
    assert client.delete(path).status_code == 428
    assert client.delete(path, headers={"If-Match": '"999"'}).status_code == 412
    assert client.delete(path, headers={"If-Match": f'"{current["version"]}"'}).status_code == 202
    assert client.get(path + "/preview").status_code == 410
    assert worker.run("deletion_worker")["outcome"] == "ok"
    assert not reopened.exists(stored_key)
    receipts = client.get(path + "/receipts").json()["receipts"]
    assert len(receipts) == 1 and set(receipts[0]) == {"receipt_id", "verified_at", "expires_at"}
    assert client.get(path).json()["status"] == "deleted"
    assert client.delete(path).status_code == 204
    assert transfer(client, intent, data).status_code == 410
    # Restored bytes cannot survive an independent receipt-ledger reconciliation.
    # Simulate an out-of-band backup restore, never the adapter's fenced write API.
    (service.storage.root / str(stored_key)).write_bytes(snapshot)
    with pytest.raises(AppError):
        reopened.read(provider.user, stored_key)
    assert worker.run("reconciliation")["outcome"] == "ok"
    assert not reopened.exists(stored_key)
    assert client.get(path + "/receipts").json()["receipts"] == receipts


def test_idempotency_quota_ticket_replay_and_completion(uploads):
    client, service, worker, data, *_ = uploads
    key = uuid4()
    first = initiate(client, data, key=key).json()
    second = initiate(client, data, key=key).json()
    assert second["upload_id"] == first["upload_id"] and second["ticket"] is None
    assert initiate(client, data, key=key, document_kind="tube").status_code == 409
    assert transfer(client, {**first, "ticket": "invalid"}, data).status_code == 403
    assert transfer(client, first, data).status_code == 204
    assert transfer(client, first, data).status_code == 410
    result = complete(client, first, data)
    assert result.status_code == 200
    assert complete(client, first, data).json() == result.json()
    for kind in ("strip", "bottle", "tube", "prescription"):
        assert initiate(client, data, document_kind=kind).status_code == 201
    assert initiate(client, data).status_code == 429


def test_owner_isolation_all_routes_and_database_roles(uploads):
    client, service, worker, data, engine, provider, _ = uploads
    intent, current, path = accepted(client, data)
    owner = provider.user
    provider.user, provider.sid = uuid4(), uuid4()
    for suffix in ("", "/preview", "/receipts"):
        assert client.get(path + suffix).status_code == 404
    assert client.delete(path, headers={"If-Match": '"1"'}).status_code == 404
    assert transfer(client, intent, data).status_code == 404
    assert (
        client.post(
            path + "/complete",
            json={"checksum_sha256": hashlib.sha256(data).hexdigest()},
            headers={"Idempotency-Key": str(uuid4()), "If-Match": '"1"'},
        ).status_code
        == 404
    )
    with client.app.state.database.transaction() as conn:
        assert sql(conn, "SELECT count(*) FROM medlm.uploads").scalar_one() == 0
    with client.app.state.database.transaction(owner) as conn:
        assert sql(conn, "SELECT count(*) FROM medlm.uploads").scalar_one() == 1
    with worker.db.transaction() as conn:
        assert sql(conn, "SELECT count(*) FROM medlm.uploads").scalar_one() == 1
    with pytest.raises(DBAPIError), worker.db.transaction() as conn:
        sql(conn, "SELECT * FROM medlm_auth.web_sessions")
    with pytest.raises(DBAPIError), client.app.state.database.transaction(owner) as conn:
        sql(
            conn,
            "INSERT INTO medlm.upload_deletion_receipts VALUES (:id,:uid,:key,now(),now()+interval '1 day')",
            id=uuid4(),
            uid=owner,
            key=uuid4(),
        )


@pytest.mark.parametrize(
    "case", ["unknown", "oversize", "mismatch", "mime", "invalid", "dimensions"]
)
def test_rejects_unsafe_inputs_without_persisting_images(uploads, case):
    client, service, worker, data, *_ = uploads
    if case == "unknown":
        assert initiate(client, data, user_id=str(uuid4())).status_code == 422
        assert initiate(client, b"not a fixture").status_code == 403
        return
    if case == "invalid":
        data = b"invalid synthetic image"
        service.allowed = frozenset([hashlib.sha256(data).hexdigest()])
    if case == "dimensions":
        client.app.state.settings.max_image_pixels = 1
    intent = initiate(client, data).json()
    if case == "mime":
        response = client.put(
            "/api/v1" + intent["upload_url"],
            content=data,
            headers={"Content-Type": "text/html", "X-Upload-Ticket": intent["ticket"]},
        )
        assert response.status_code == 415
    else:
        payload = (
            data + b"extra"
            if case == "oversize"
            else (b"x" * len(data) if case == "mismatch" else data)
        )
        response = transfer(client, intent, payload)
        assert (
            response.status_code
            == {"oversize": 413, "mismatch": 403, "invalid": 422, "dimensions": 422}[case]
        ), response.text
    assert service.storage.keys() == []


def test_expiry_sweep_is_independent_of_queue_and_receipt_outlives_user(uploads):
    client, service, worker, data, engine, provider, _ = uploads
    service.ttl = 1800
    intent, current, path = accepted(client, data)
    with worker.db.transaction() as conn:
        assert sql(conn, "SELECT count(*) FROM medlm.upload_deletion_jobs").scalar_one() == 0
    future = utcnow() + timedelta(minutes=45)
    service.clock = worker.clock = lambda: future
    assert client.get(path + "/preview").status_code == 410
    assert worker.run("independent_sweep")["outcome"] == "ok"
    assert service.storage.keys() == []
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM medlm.users WHERE id=:id"), {"id": provider.user})
        assert (
            conn.scalar(
                text("SELECT count(*) FROM medlm.upload_deletion_receipts WHERE user_id IS NULL")
            )
            == 1
        )


def test_failure_blocks_admission_retries_and_never_fakes_receipt(uploads, monkeypatch):
    client, service, worker, data, *_ = uploads
    _, current, path = accepted(client, data)
    client.delete(path, headers={"If-Match": f'"{current["version"]}"'})
    real_delete = service.storage.delete
    monkeypatch.setattr(service.storage, "delete", lambda key: None)
    assert worker.run("deletion_worker")["outcome"] == "failed"
    assert client.get(path + "/receipts").json()["receipts"] == []
    assert initiate(client, data).status_code == 503
    with worker.db.transaction() as conn:
        row = sql(conn, "SELECT * FROM medlm.upload_deletion_jobs").one()
        assert row.state == "retry" and row.fencing_token == 1
    monkeypatch.setattr(service.storage, "delete", real_delete)
    # Separate sweep succeeds without waiting for failed queue retry.
    assert worker.run("independent_sweep")["outcome"] == "ok"
    assert len(client.get(path + "/receipts").json()["receipts"]) == 1
    worker.clock = lambda: utcnow() + timedelta(minutes=2)
    assert worker.run("deletion_worker")["outcome"] == "ok"
    with worker.db.transaction() as conn:
        row = sql(conn, "SELECT * FROM medlm.upload_deletion_jobs").one()
        assert row.state == "completed" and row.fencing_token == 2 and row.attempts == 2


def test_cancellation_fences_late_upload_and_logout_blocks_write(uploads):
    client, service, worker, data, engine, provider, _ = uploads
    intent = initiate(client, data).json()
    principal = provider.verify("synthetic-access")
    upload_id = UUID(intent["upload_id"])
    service.reserve(client.app.state.database, principal, upload_id, intent["ticket"], "image/png")
    current = client.get(f"/api/v1/uploads/{upload_id}").json()
    service.delete(client.app.state.database, principal, upload_id, f'"{current["version"]}"')
    worker.run("independent_sweep")
    with pytest.raises(AppError) as error:
        service.write(
            client.app.state.database, principal, upload_id, data, client.app.state.settings
        )
    assert error.value.status == 410 and service.storage.keys() == []
    # Re-establish healthy admission, reserve, then revoke during the transfer gap.
    for kind in ("deletion_worker", "reconciliation"):
        worker.run(kind)
    intent = initiate(client, data).json()
    upload_id = UUID(intent["upload_id"])
    service.reserve(client.app.state.database, principal, upload_id, intent["ticket"], "image/png")
    assert client.delete("/api/v1/auth/session").status_code == 204
    with pytest.raises(AppError) as error:
        service.write(
            client.app.state.database, principal, upload_id, data, client.app.state.settings
        )
    assert error.value.status == 401 and service.storage.keys() == []


def test_concurrent_ticket_single_acceptance_and_default_app_denial(uploads):
    client, service, worker, data, engine, provider, _ = uploads
    intent = initiate(client, data).json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(lambda _: transfer(client, intent, data).status_code, range(2)))
    assert sorted(codes) == [204, 410]
    normal = create_app(Settings(_env_file=None, environment="test", database_url=None))
    with TestClient(normal) as plain:
        assert plain.post("/api/v1/uploads", json={}).status_code == 404
    with pytest.raises(ValueError):
        create_app(Settings(_env_file=None, environment="development"), synthetic_uploads=service)


def test_nonreview_completion_deletes_and_reconciliation_finds_orphans(uploads):
    client, service, worker, data, *_ = uploads
    _, current, path = accepted(client, data, review=False)
    assert current["status"] == "deleting"
    assert client.get(path + "/preview").status_code == 410
    worker.run("deletion_worker")
    orphan = uuid4()
    service.storage.put(uuid4(), orphan, data)
    worker.run("reconciliation")
    assert service.storage.keys() == []
    with worker.db.transaction() as conn:
        assert sql(conn, "SELECT count(*) FROM medlm.upload_deletion_receipts").scalar_one() == 2


def test_browser_csrf_and_upload_preflight(uploads):
    client, service, worker, data, *_ = uploads
    client.headers.pop("authorization")
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "synthetic@example.org", "password": "synthetic-password"},
        headers={"Origin": "http://localhost:8080"},
    )
    assert login.status_code == 200
    assert initiate(client, data).status_code == 403
    client.headers.update(
        {"Origin": "http://localhost:8080", "X-CSRF-Token": login.json()["csrf_token"]}
    )
    intent, current, path = accepted(client, data)
    assert client.get(path + "/preview").status_code == 200
    preflight = client.options(
        "/api/v1" + intent["upload_url"],
        headers={
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "X-Upload-Ticket,If-Match,Idempotency-Key",
        },
    )
    assert preflight.status_code == 200


def test_migration_from_chunk2_and_roundtrip(isolated_database):
    engine, cfg = isolated_database
    command.upgrade(cfg, "0003_auth_session_hardening")
    owner, upload_id = uuid4(), uuid4()
    with engine.begin() as conn:
        sql(conn, "INSERT INTO medlm.users(id) VALUES (:id)", id=owner)
        sql(
            conn,
            """INSERT INTO medlm.uploads
            (id,user_id,notice_version,document_kind,mime,declared_bytes,ticket_hash,
             ticket_expires_at,expires_at)
            VALUES (:id,:uid,'synthetic-v1','box','image/png',1,:hash,
                    now()+interval '5 minutes',now()+interval '1 hour')""",
            id=upload_id,
            uid=owner,
            hash="b" * 64,
        )
        original = sql(conn, "SELECT * FROM medlm.uploads").mappings().one()
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        upgraded = sql(conn, "SELECT * FROM medlm.uploads").mappings().one()
        assert all(upgraded[k] == v for k, v in original.items())
        assert upgraded.request_key is None and upgraded.source_checksum_sha256 is None
    command.downgrade(cfg, "0003_auth_session_hardening")
    with engine.connect() as conn:
        assert sql(conn, "SELECT * FROM medlm.uploads").mappings().one() == original
    command.upgrade(cfg, "head")


@pytest.mark.parametrize("format,mime", [("JPEG", "image/jpeg"), ("WEBP", "image/webp")])
def test_additional_image_formats_are_sanitized_to_png(uploads, format, mime):
    client, service, worker, data, *_ = uploads
    data = fixture_image(format)
    service.allowed = frozenset([hashlib.sha256(data).hexdigest()])
    intent = initiate(client, data, content_type=mime).json()
    response = client.put(
        "/api/v1" + intent["upload_url"],
        content=data,
        headers={"Content-Type": mime, "X-Upload-Ticket": intent["ticket"]},
    )
    assert response.status_code == 204
    assert complete(client, intent, data).status_code == 200
    preview = client.get(f"/api/v1/uploads/{intent['upload_id']}/preview")
    assert preview.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_interrupted_storage_write_is_inventoried_and_swept(uploads, monkeypatch):
    client, service, worker, data, *_ = uploads
    intent = initiate(client, data).json()

    def interrupted(owner, key, content):
        (service.storage.root / str(key)).write_bytes(b"partial encrypted synthetic write")
        raise OSError("synthetic private path that must not be returned")

    monkeypatch.setattr(service.storage, "put", interrupted)
    response = transfer(client, intent, data)
    assert response.status_code == 503
    assert "private path" not in response.text
    assert len(service.storage.keys()) == 1
    worker.run("independent_sweep")
    assert service.storage.keys() == []
    assert (
        len(client.get(f"/api/v1/uploads/{intent['upload_id']}/receipts").json()["receipts"]) == 1
    )


def test_logout_serializes_with_last_storage_write(uploads, monkeypatch):
    client, service, worker, data, engine, provider, _ = uploads
    intent = initiate(client, data).json()
    principal = provider.verify("synthetic-access")
    upload_id = UUID(intent["upload_id"])
    db = client.app.state.database
    service.reserve(db, principal, upload_id, intent["ticket"], "image/png")
    entered, release, attempting = threading.Event(), threading.Event(), threading.Event()
    original = service.storage.put

    def paused(owner, key, content):
        entered.set()
        assert release.wait(5)
        original(owner, key, content)

    monkeypatch.setattr(service.storage, "put", paused)

    def logout():
        attempting.set()
        client.app.state.auth.logout_native("synthetic-access")

    with ThreadPoolExecutor(max_workers=2) as pool:
        writing = pool.submit(
            service.write, db, principal, upload_id, data, client.app.state.settings
        )
        assert entered.wait(5)
        revoking = pool.submit(logout)
        try:
            assert attempting.wait(5)
            assert not revoking.done()
        finally:
            release.set()
        writing.result(timeout=5)
        revoking.result(timeout=5)
    assert client.get(f"/api/v1/uploads/{upload_id}/preview").status_code == 401


def test_ticket_expiry_and_stale_health_deny_admission(uploads):
    client, service, worker, data, *_ = uploads
    real_clock = service.clock
    service.clock = lambda: real_clock() - timedelta(minutes=10)
    intent = initiate(client, data).json()
    service.clock = real_clock
    assert transfer(client, intent, data).status_code == 410
    worker.run("independent_sweep")
    service.clock = lambda: real_clock() + timedelta(minutes=6)
    assert initiate(client, data).status_code == 503


def test_independent_ledger_restores_missing_database_receipt(uploads):
    client, service, worker, data, engine, provider, key = uploads
    _, current, path = accepted(client, data)
    stored_key = service.storage.keys()[0]
    snapshot = (service.storage.root / str(stored_key)).read_bytes()
    client.delete(path, headers={"If-Match": f'"{current["version"]}"'})
    worker.run("deletion_worker")
    # Simulate the receipts relation being restored from an older empty snapshot.
    # TRUNCATE is only performed by the disposable database owner, never runtime.
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE medlm.upload_deletion_receipts"))
    (service.storage.root / str(stored_key)).write_bytes(snapshot)
    reopened = LocalSyntheticStorage(service.storage.root, key)
    with pytest.raises(AppError):
        reopened.read(provider.user, stored_key)
    worker.run("reconciliation")
    assert not service.storage.exists(stored_key)
    assert len(client.get(path + "/receipts").json()["receipts"]) == 1


def test_api_role_cannot_run_cross_owner_maintenance(uploads):
    client, service, worker, data, *_ = uploads
    incorrect = UploadMaintenance(client.app.state.database, service.storage)
    with pytest.raises(ValueError):
        incorrect.run("reconciliation")
    intent, current, path = accepted(client, data)
    with pytest.raises(DBAPIError), client.app.state.database.transaction() as conn:
        sql(conn, "UPDATE medlm.upload_objects SET purged_at=now()")
    with pytest.raises(DBAPIError), client.app.state.database.transaction() as conn:
        sql(conn, "UPDATE medlm.upload_deletion_jobs SET state='completed'")


def test_receipt_storage_failure_is_not_reported_as_verified_deletion(uploads, monkeypatch):
    client, service, worker, data, *_ = uploads
    _, current, path = accepted(client, data)
    client.delete(path, headers={"If-Match": f'"{current["version"]}"'})
    original = service.storage.record_deletion

    def fail(*args):
        raise OSError("receipt disk unavailable")

    monkeypatch.setattr(service.storage, "record_deletion", fail)
    assert worker.run("deletion_worker")["outcome"] == "failed"
    assert client.get(path + "/receipts").json()["receipts"] == []
    assert client.get(path).json()["status"] == "deleting"
    monkeypatch.setattr(service.storage, "record_deletion", original)
    assert worker.run("independent_sweep")["outcome"] == "ok"
    assert len(client.get(path + "/receipts").json()["receipts"]) == 1


def test_storage_rejects_path_keys_wrong_key_and_overwrite(uploads):
    client, service, worker, data, engine, provider, key = uploads
    accepted(client, data)
    object_key = service.storage.keys()[0]
    with pytest.raises(ValueError):
        service.storage.read(provider.user, "../outside")
    with pytest.raises(FileExistsError):
        service.storage.put(provider.user, object_key, data)
    wrong = LocalSyntheticStorage(service.storage.root, Fernet.generate_key())
    with pytest.raises(OSError):
        wrong.read(provider.user, object_key)


def test_harness_contract_and_normal_contract_are_separate(uploads):
    client, *_ = uploads
    import json

    expected = json.loads((ROOT / "contracts/synthetic-openapi.json").read_text())
    assert client.app.openapi() == expected
    normal = create_app(Settings(_env_file=None, environment="test", database_url=None))
    assert normal.openapi() == json.loads((ROOT / "contracts/openapi.json").read_text())
    normal.state.database.close()
    normal.state.auth.gateway.close()


def test_stream_timeout_queues_cleanup(uploads, monkeypatch):
    import asyncio

    import httpx
    import medlm_api.upload_routes as routes

    client, service, worker, data, *_ = uploads
    intent = initiate(client, data).json()
    monkeypatch.setattr(routes, "TRANSFER_SECONDS", 0.1)

    async def slow_body():
        yield data[:1]
        await asyncio.sleep(1)
        yield data[1:]

    async def send():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=client.app), base_url="http://testserver"
        ) as sender:
            return await sender.put(
                "/api/v1" + intent["upload_url"],
                content=slow_body(),
                headers={
                    "Authorization": "Bearer synthetic-access",
                    "Content-Type": "image/png",
                    "X-Upload-Ticket": intent["ticket"],
                },
            )

    response = asyncio.run(send())
    assert response.status_code == 408
    worker.run("independent_sweep")
    assert service.storage.keys() == []
    assert client.get(f"/api/v1/uploads/{intent['upload_id']}").json()["status"] == "deleted"


def test_independent_worker_commands(uploads):
    import json
    import os
    import subprocess
    import sys

    client, service, worker, data, engine, provider, key = uploads
    accepted(client, data, review=False)
    environment = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "services/api"),
        "MEDLM_ENVIRONMENT": "test",
        "MEDLM_UPLOAD_WORKER_DATABASE_URL": worker.db.engine.url.render_as_string(
            hide_password=False
        ),
        "MEDLM_SYNTHETIC_STORAGE_ROOT": str(service.storage.root),
        "MEDLM_SYNTHETIC_STORAGE_KEY": key.decode(),
    }
    for kind in ("deletion_worker", "independent_sweep", "reconciliation"):
        result = subprocess.run(
            [sys.executable, "-m", "medlm_api.upload_maintenance", kind],
            env=environment,
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
        assert json.loads(result.stdout) == {"kind": kind, "outcome": "ok", "overdue_objects": 0}
    assert service.storage.keys() == []

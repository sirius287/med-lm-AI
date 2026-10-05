from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import text
from test_auth_sessions import auth_env as _auth_fixture
from test_upload_schema import isolated_database as _database_fixture

isolated_database = _database_fixture
auth_env = _auth_fixture
ROOT = Path(__file__).resolve().parents[3]
BODY = {
    "display_name": "Synthetic entry",
    "dose_text": "User-entered instruction",
    "strength_text": "Literal strength",
}


@pytest.fixture
def manual(auth_env):
    engine, settings, provider, app = auth_env
    settings.medication_encryption_key = Fernet.generate_key().decode()
    # Assignment is deliberately rebuilt through validation (SecretStr).
    from medlm_api.config import Settings
    from medlm_api.main import create_app

    settings = Settings(**settings.model_dump())
    with engine.begin() as conn:
        conn.execute(text((ROOT / "database/runtime_grants.sql").read_text()))
    with TestClient(create_app(settings, provider)) as client:
        client.headers["Authorization"] = "Bearer synthetic-access"
        yield client, engine, provider


def post(client, path, body, key=None):
    return client.post(
        "/api/v1" + path, json=body, headers={"Idempotency-Key": str(key or uuid4())}
    )


def create(client):
    response = post(client, "/medications", BODY)
    assert response.status_code == 201, response.text
    return response.json()


def activate(client, record):
    now = datetime.now(UTC)
    body = dict(
        kind="fixed_interval",
        time_zone="Asia/Kolkata",
        start_date=(now - timedelta(days=1)).date().isoformat(),
        open_ended=True,
        interval_hours="1",
        anchor_at=(now + timedelta(seconds=1)).isoformat(),
    )
    response = post(client, f"/medications/{record['id']}/schedules/preview", body)
    assert response.status_code == 200, response.text
    preview = response.json()
    response = post(
        client,
        f"/medications/{record['id']}/schedules",
        dict(
            schedule=body,
            proposal_hash=preview["proposal_hash"],
            expires_at=preview["expires_at"],
            medication_version=preview["medication_version"],
        ),
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize("start_offset,expected", [(641, 200), (642, 422), (731, 422)])
def test_preview_and_activation_share_materialization_bounds(
    manual, monkeypatch, start_offset, expected
):
    from medlm_api import medication_service

    client, engine, _ = manual
    now = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)
    monkeypatch.setattr(medication_service, "utcnow", lambda: now)
    record = create(client)
    schedule = dict(
        kind="daily_times",
        time_zone="Asia/Kolkata",
        start_date=(now.date() + timedelta(days=start_offset)).isoformat(),
        open_ended=True,
        local_times=["08:00"],
    )
    response = post(client, f"/medications/{record['id']}/schedules/preview", schedule)
    assert response.status_code == expected, response.text
    if expected == 200:
        preview = response.json()
        activated = post(
            client,
            f"/medications/{record['id']}/schedules",
            dict(
                schedule=schedule,
                proposal_hash=preview["proposal_hash"],
                expires_at=preview["expires_at"],
                medication_version=preview["medication_version"],
            ),
        )
        assert activated.status_code == 201, activated.text
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT count(*) FROM medlm.dose_occurrences")) == 90
    else:
        assert response.json()["error"]["code"] == "invalid_range"
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT count(*) FROM medlm.medication_schedules")) == 0
            assert conn.scalar(text("SELECT count(*) FROM medlm.dose_occurrences")) == 0


def test_crud_idempotency_versions_and_disabled_uploads(manual):
    client, engine, provider = manual
    key = uuid4()
    a = post(client, "/medications", BODY, key)
    b = post(client, "/medications", BODY, key)
    assert a.status_code == b.status_code == 201, a.text
    assert a.json() == b.json()
    assert post(client, "/medications", BODY | {"dose_text": "Different"}, key).status_code == 409
    id = a.json()["id"]
    assert client.get("/api/v1/medications").json()["items"][0]["id"] == id
    assert client.patch(f"/api/v1/medications/{id}", json=BODY).status_code == 428
    assert (
        client.patch(
            f"/api/v1/medications/{id}", json=BODY, headers={"If-Match": '"99"'}
        ).status_code
        == 412
    )
    updated = client.patch(
        f"/api/v1/medications/{id}",
        json=BODY | {"display_name": "Changed"},
        headers={"If-Match": '"1"'},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2
    assert (
        client.delete(f"/api/v1/medications/{id}", headers={"If-Match": '"2"'}).status_code == 204
    )
    assert (
        client.delete(f"/api/v1/medications/{id}", headers={"If-Match": '"2"'}).status_code == 204
    )
    assert client.get("/api/v1/medications").json()["items"] == []
    assert post(client, "/medications", BODY, key).status_code == 410
    assert client.post("/api/v1/uploads", json={}).status_code == 404


def test_schedule_events_history_and_erasure(manual):
    client, engine, provider = manual
    record = activate(client, create(client))
    with engine.begin() as conn:
        # Test clock passage without mutating the immutable occurrence snapshot.
        first = conn.execute(
            text("SELECT id,planned_at FROM medlm.dose_occurrences ORDER BY planned_at LIMIT 1")
        ).first()
    import time

    time.sleep(max(0, (first.planned_at - datetime.now(UTC)).total_seconds()) + 0.05)
    body = dict(
        event_id=str(uuid4()),
        type="taken",
        expected_version=1,
        client_at=datetime.now(UTC).isoformat(),
    )
    event = post(client, f"/occurrences/{first.id}/events", body)
    assert event.status_code == 201, event.text
    assert post(client, f"/occurrences/{first.id}/events", body).status_code == 201
    assert (
        post(
            client,
            f"/occurrences/{first.id}/events",
            body | {"event_id": str(uuid4()), "type": "skipped"},
        ).status_code
        == 409
    )
    correction = dict(
        event_id=str(uuid4()),
        type="corrected",
        expected_version=2,
        client_at=datetime.now(UTC).isoformat(),
        supersedes_event_id=body["event_id"],
        corrected_status="skipped",
    )
    response = post(client, f"/occurrences/{first.id}/events", correction)
    assert response.status_code == 201, response.text
    assert response.json()["occurrence"]["status"] == "skipped"
    today = datetime.now(UTC).date()
    query = f"?from_date={today - timedelta(days=1)}&to_date={today + timedelta(days=1)}"
    history = client.get("/api/v1/history" + query)
    assert history.status_code == 200, history.text
    assert len(history.json()["items"]) == 2
    assert history.json()["items"][0]["dose_snapshot"]["display_name"] == BODY["display_name"]
    assert (
        client.delete(
            f"/api/v1/medications/{record['id']}?erase_history=true",
            headers={"If-Match": f'"{record["version"]}"'},
        ).status_code
        == 204
    )
    assert client.get("/api/v1/history" + query).json()["items"] == []
    assert (
        client.delete(
            f"/api/v1/medications/{record['id']}?erase_history=true",
            headers={"If-Match": f'"{record["version"]}"'},
        ).status_code
        == 204
    )
    with engine.connect() as conn:
        assert (
            conn.scalar(
                text(
                    "SELECT count(*) FROM medlm.idempotency_records WHERE resource_id=:id AND encrypted_response<>''"
                ),
                {"id": record["id"]},
            )
            == 0
        )


def test_cross_owner_csrf_revocation_and_no_input_echo(manual):
    client, engine, provider = manual
    record = create(client)
    original = provider.user
    provider.user = uuid4()
    assert client.get(f"/api/v1/medications/{record['id']}").status_code == 404
    assert client.get("/api/v1/medications").json()["items"] == []
    assert (
        client.patch(
            f"/api/v1/medications/{record['id']}", json=BODY, headers={"If-Match": '"1"'}
        ).status_code
        == 404
    )
    provider.user = original
    bad = post(
        client, "/medications", BODY | {"origin": "confirmed_prescription", "dose_text": " "}
    )
    assert bad.status_code == 422 and BODY["display_name"] not in bad.text
    client.headers.pop("Authorization")
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.org", "password": "synthetic-password"},
        headers={"Origin": "http://localhost:8080"},
    )
    assert login.status_code == 200
    assert post(client, "/medications", BODY).status_code == 403
    client.headers.update(
        {"Origin": "http://localhost:8080", "X-CSRF-Token": login.json()["csrf_token"]}
    )
    assert post(client, "/medications", BODY).status_code == 201
    assert client.delete("/api/v1/auth/session").status_code == 204
    assert client.get("/api/v1/medications").status_code == 401


def test_request_waiting_behind_logout_cannot_write(manual):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from fastapi import Request
    from medlm_api.auth_dependencies import current_identity

    client, engine, _ = manual
    entered, resume = threading.Event(), threading.Event()

    def identity_before_transaction(request: Request):
        identity = current_identity(request)
        entered.set()
        assert resume.wait(10)
        return identity

    client.app.dependency_overrides[current_identity] = identity_before_transaction
    other = TestClient(client.app)
    other.headers["Authorization"] = "Bearer synthetic-access"
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(post, other, "/medications", BODY)
            assert entered.wait(10)
            try:
                assert client.delete("/api/v1/auth/session").status_code == 204
            finally:
                resume.set()
            assert pending.result(timeout=10).status_code == 401
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT count(*) FROM medlm.medications")) == 0
    finally:
        resume.set()
        client.app.dependency_overrides.clear()
        other.close()

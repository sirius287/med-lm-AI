from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import text
from test_manual_medication_api import BODY, post
from test_manual_medication_api import auth_env as _auth
from test_manual_medication_api import isolated_database as _database
from test_manual_medication_api import manual as _manual

auth_env, isolated_database, manual = _auth, _database, _manual


def test_response_encryption_expiry_and_deletion_tombstone(manual):
    client, engine, _ = manual
    key = uuid4()
    result = post(client, "/medications", BODY, key)
    assert result.status_code == 201
    with engine.begin() as conn:
        encrypted = conn.scalar(
            text("SELECT encrypted_response FROM medlm.idempotency_records WHERE key=:key"),
            {"key": key},
        )
        assert BODY["display_name"] not in encrypted
        conn.execute(
            text("UPDATE medlm.idempotency_records SET expires_at=:at WHERE key=:key"),
            {"at": datetime.now(UTC) - timedelta(seconds=1), "key": key},
        )
    assert post(client, "/medications", BODY, key).json()["id"] != result.json()["id"]


def test_missing_key_and_no_user_override(manual):
    client, _, _ = manual
    assert client.post("/api/v1/medications", json=BODY).status_code == 428
    assert post(client, "/medications", BODY | {"user_id": str(uuid4())}).status_code == 422
    assert post(client, "/medications", BODY | {"product_id": str(uuid4())}).status_code == 422


def test_expiry_only_maintenance_role_cannot_read_live_requests(manual):
    from pathlib import Path

    client, engine, _ = manual
    first, second = uuid4(), uuid4()
    assert post(client, "/medications", BODY, first).status_code == 201
    assert post(client, "/medications", BODY, second).status_code == 201
    with engine.begin() as conn:
        conn.execute(
            text("""DO $$ BEGIN
          IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='medlm_medication_maintenance') THEN
            CREATE ROLE medlm_medication_maintenance NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
          END IF; END $$""")
        )
        conn.execute(
            text(
                (
                    Path(__file__).resolve().parents[3]
                    / "database/medication_maintenance_grants.sql"
                ).read_text()
            )
        )
        conn.execute(
            text(
                "UPDATE medlm.idempotency_records SET expires_at=now()-interval '1 second' WHERE key=:key"
            ),
            {"key": first},
        )
        conn.execute(text("SET LOCAL ROLE medlm_medication_maintenance"))
        assert conn.execute(text("SELECT key FROM medlm.idempotency_records")).scalars().all() == [
            first
        ]
        assert (
            conn.execute(
                text("DELETE FROM medlm.idempotency_records WHERE expires_at<=now()")
            ).rowcount
            == 1
        )
        assert conn.scalar(text("SELECT count(*) FROM medlm.idempotency_records")) == 0
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM medlm.idempotency_records")) == 1

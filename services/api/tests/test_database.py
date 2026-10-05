import json
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from medlm_api.auth import Principal
from medlm_api.config import Settings
from medlm_api.database import Database
from medlm_api.errors import AppError
from medlm_api.main import create_app
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.database


@pytest.fixture
def database_url():
    value = os.getenv("MEDLM_TEST_DATABASE_URL")
    if not value:
        pytest.skip("MEDLM_TEST_DATABASE_URL not configured; no database claim is made")
    return value


def test_connectivity_migration_and_empty_clinical_tables(database_url):
    db = Database(Settings(_env_file=None, environment="test", database_url=database_url))
    assert db.ping()
    with db.transaction() as conn:
        expected = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == expected
        for table in ("medications", "prescriptions", "verification_sources", "dose_events"):
            assert conn.scalar(text(f"SELECT count(*) FROM medlm.{table}")) == 0
    db.close()


def test_real_postgres_rls_isolation(database_url):
    engine = create_engine(database_url)
    first, second = uuid4(), uuid4()
    # Entire transaction rolls back; synthetic identities only, no medical records.
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            for user in (first, second):
                conn.execute(text("INSERT INTO medlm.users(id) VALUES (:id)"), {"id": user})
                conn.execute(text("INSERT INTO medlm.profiles(user_id) VALUES (:id)"), {"id": user})
            conn.execute(text("SET LOCAL ROLE medlm_runtime"))
            conn.execute(text("SELECT set_config('app.user_id',:id,true)"), {"id": str(first)})
            assert conn.execute(text("SELECT user_id FROM medlm.profiles")).scalars().all() == [
                first
            ]
            assert (
                conn.execute(
                    text("UPDATE medlm.profiles SET locale='hi-IN' WHERE user_id=:id"),
                    {"id": second},
                ).rowcount
                == 0
            )
            with pytest.raises(DBAPIError):
                with conn.begin_nested():
                    conn.execute(text("SELECT * FROM medlm.medications"))
        finally:
            transaction.rollback()
    engine.dispose()


def test_web_session_lifecycle_and_csrf(database_url):
    user_id, session_id = uuid4(), uuid4()

    class Provider:
        refresh_calls = 0

        def register(self, email, password):
            pass

        def login(self, email, password):
            return {
                "access_token": "synthetic-access",
                "refresh_token": "synthetic-refresh",
                "expires_in": 3600,
            }

        def verify(self, token):
            if token != "synthetic-access":
                raise AppError(401, "invalid_session", "Sign in again.")
            return Principal(user_id, session_id, datetime.now(UTC) + timedelta(hours=1))

        def refresh(self, token):
            assert token == "synthetic-refresh"
            self.refresh_calls += 1
            return self.login("", "")

        def logout(self, token):
            pass

        def close(self):
            pass

    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=make_url(database_url)
        .update_query_dict({"options": "-c role=medlm_runtime"})
        .render_as_string(hide_password=False),
        session_encryption_key=Fernet.generate_key().decode(),
    )
    engine = create_engine(database_url)
    provider = Provider()
    try:
        with TestClient(create_app(settings, provider)) as client:
            headers = {"Origin": "http://localhost:8080"}
            response = client.post(
                "/api/v1/auth/login",
                headers=headers,
                json={"email": "person@example.org", "password": "synthetic-test-password"},
            )
            assert response.status_code == 200
            assert "HttpOnly" in response.headers["set-cookie"]
            assert "synthetic-access" not in response.text
            csrf = response.json()["csrf_token"]
            assert client.get("/api/v1/auth/session").json()["user_id"] == str(user_id)
            assert client.get("/api/v1/health/database").status_code == 200
            # Force expiry in the encrypted server session, then exercise rotation.
            cipher = Fernet(settings.session_encryption_key.get_secret_value().encode())
            with engine.begin() as conn:
                encrypted = conn.scalar(
                    text("SELECT encrypted_tokens FROM medlm_auth.web_sessions WHERE user_id=:id"),
                    {"id": user_id},
                )
                assert "synthetic-refresh" not in encrypted
                tokens = json.loads(cipher.decrypt(encrypted.encode()))
                tokens["expires_at"] = 0
                conn.execute(
                    text(
                        "UPDATE medlm_auth.web_sessions SET encrypted_tokens=:tokens WHERE user_id=:id"
                    ),
                    {"id": user_id, "tokens": cipher.encrypt(json.dumps(tokens).encode()).decode()},
                )
            assert client.get("/api/v1/auth/session").status_code == 200
            assert provider.refresh_calls == 1
            assert client.delete("/api/v1/auth/session", headers=headers).status_code == 403
            assert (
                client.delete(
                    "/api/v1/auth/session", headers={**headers, "X-CSRF-Token": csrf}
                ).status_code
                == 204
            )
            assert client.get("/api/v1/auth/session").status_code == 401
            assert (
                client.get(
                    "/api/v1/auth/session", headers={"Authorization": "Bearer synthetic-access"}
                ).status_code
                == 401
            )
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM medlm.users WHERE id=:id"), {"id": user_id})
        engine.dispose()

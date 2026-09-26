import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from alembic import command
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends
from fastapi.testclient import TestClient
from medlm_api.auth import Principal, SupabaseGateway, digest
from medlm_api.auth_dependencies import owned_connection
from medlm_api.auth_rate_limit import AuthRateLimiter
from medlm_api.config import Settings
from medlm_api.errors import AppError
from medlm_api.main import create_app
from medlm_api.session_maintenance import cleanup
from pydantic import ValidationError
from sqlalchemy import text
from test_upload_schema import isolated_database as _database_fixture

isolated_database = _database_fixture


class Provider:
    def __init__(self):
        self.user, self.sid = uuid4(), uuid4()
        self.refresh_calls = 0
        self.offline = False
        self.changed_sid = False
        self.entered = None
        self.resume = None

    def register(self, *args):
        return {}

    def login(self, *args):
        return {"access_token": "synthetic-access", "refresh_token": "synthetic-refresh"}

    def verify_local(self, token, *, allow_expired=False):
        if token not in ("synthetic-access", "synthetic-new"):
            raise AppError(401, "invalid_session", "Sign in again.")
        sid = uuid4() if self.changed_sid and token == "synthetic-new" else self.sid
        return Principal(self.user, sid, datetime.now(UTC) + timedelta(hours=1))

    def verify(self, token):
        if self.offline:
            raise AppError(503, "auth_unavailable", "Unavailable", True)
        return self.verify_local(token)

    def refresh(self, token):
        self.refresh_calls += 1
        if self.entered:
            self.entered.set()
            assert self.resume.wait(5)
        if self.offline:
            raise AppError(503, "auth_unavailable", "Unavailable", True)
        return {"access_token": "synthetic-new", "refresh_token": "synthetic-refresh-new"}

    def logout(self, token):
        if self.offline:
            raise AppError(503, "auth_unavailable", "Unavailable", True)

    def close(self):
        pass


@pytest.fixture
def auth_env(isolated_database):
    engine, cfg = isolated_database
    command.upgrade(cfg, "head")
    with engine.begin() as conn:
        conn.execute(text("GRANT USAGE ON SCHEMA medlm,medlm_auth TO medlm_runtime"))
        conn.execute(
            text("GRANT SELECT,INSERT,UPDATE ON medlm.users,medlm.profiles TO medlm_runtime")
        )
        conn.execute(
            text(
                "GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA medlm_auth TO medlm_runtime"
            )
        )
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=engine.url.update_query_dict(
            {"options": "-c role=medlm_runtime"}
        ).render_as_string(hide_password=False),
        session_encryption_key=Fernet.generate_key().decode(),
        auth_rate_limit_key="synthetic-throttle-key-32-characters",
    )
    provider = Provider()
    app = create_app(settings, provider)
    try:
        yield engine, settings, provider, app
    finally:
        app.state.database.close()


def sign_in(app):
    return app.state.auth.login_web("person@example.org", "synthetic-password")


def expire_access(engine, auth, cookie):
    with engine.begin() as conn:
        payload = conn.scalar(
            text("SELECT encrypted_tokens FROM medlm_auth.web_sessions WHERE id_hash=:id"),
            {"id": digest(cookie)},
        )
        tokens = json.loads(auth.cipher().decrypt(payload.encode()))
        tokens["expires_at"] = 0
        conn.execute(
            text("UPDATE medlm_auth.web_sessions SET encrypted_tokens=:v WHERE id_hash=:id"),
            {
                "id": digest(cookie),
                "v": auth.cipher().encrypt(json.dumps(tokens).encode()).decode(),
            },
        )


def test_logout_provider_outage_atomic_and_repeatable(auth_env):
    engine, _, provider, app = auth_env
    cookie, csrf, _ = sign_in(app)
    provider.offline = True
    with TestClient(app) as client:
        client.cookies.set("medlm_session", cookie)
        origin = {"Origin": "http://localhost:8080"}
        assert client.delete("/api/v1/auth/session", headers=origin).status_code == 403
        assert (
            client.delete(
                "/api/v1/auth/session", headers={**origin, "X-CSRF-Token": csrf}
            ).status_code
            == 204
        )
        assert (
            client.delete(
                "/api/v1/auth/session", headers={**origin, "X-CSRF-Token": csrf}
            ).status_code
            == 204
        )
        client.cookies.clear()
        assert client.delete("/api/v1/auth/session", headers=origin).status_code == 204
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT revoked_at IS NOT NULL FROM medlm_auth.web_sessions"))
        assert conn.scalar(text("SELECT count(*) FROM medlm_auth.revoked_sessions")) == 1
    provider.offline = False
    with pytest.raises(AppError):
        app.state.auth.native("synthetic-access")


def test_refresh_serializes_and_does_not_extend_expiry(auth_env):
    engine, _, provider, app = auth_env
    auth = app.state.auth
    cookie, _, _ = sign_in(app)
    with engine.connect() as conn:
        expiry = conn.scalar(text("SELECT expires_at FROM medlm_auth.web_sessions"))
    expire_access(engine, auth, cookie)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: auth.web(cookie), range(2)))
    assert provider.refresh_calls == 1
    assert all(result[0].session_id == provider.sid for result in results)
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT expires_at FROM medlm_auth.web_sessions")) == expiry


def test_logout_wins_race_with_refresh(auth_env):
    engine, _, provider, app = auth_env
    auth = app.state.auth
    cookie, csrf, _ = sign_in(app)
    expire_access(engine, auth, cookie)
    provider.entered, provider.resume = threading.Event(), threading.Event()
    with ThreadPoolExecutor(2) as pool:
        refresh = pool.submit(auth.web, cookie)
        assert provider.entered.wait(5)
        logout = pool.submit(auth.logout_web, cookie, csrf)
        provider.resume.set()
        refresh.result(timeout=5)
        logout.result(timeout=5)
    with pytest.raises(AppError):
        auth.web(cookie)
    with pytest.raises(AppError):
        auth.native("synthetic-new")


@pytest.mark.parametrize("failure", ["identity", "offline"])
def test_uncertain_refresh_is_invalidated(auth_env, failure):
    engine, _, provider, app = auth_env
    cookie, _, _ = sign_in(app)
    expire_access(engine, app.state.auth, cookie)
    provider.changed_sid = failure == "identity"
    provider.offline = failure == "offline"
    with pytest.raises(AppError):
        app.state.auth.web(cookie)
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT revoked_at IS NOT NULL FROM medlm_auth.web_sessions"))


def test_legacy_binding_key_rotation_and_expiry(auth_env):
    engine, settings, provider, app = auth_env
    cookie, _, _ = sign_in(app)
    old_key = settings.session_encryption_key
    with engine.begin() as conn:
        conn.execute(text("UPDATE medlm_auth.web_sessions SET provider_session_id=NULL"))
    settings.session_encryption_key = type(old_key)(Fernet.generate_key().decode())
    settings.session_decryption_keys = [old_key]
    assert app.state.auth.web(cookie)[0].session_id == provider.sid
    with engine.begin() as conn:
        encrypted = conn.scalar(text("SELECT encrypted_tokens FROM medlm_auth.web_sessions"))
        Fernet(settings.session_encryption_key.get_secret_value().encode()).decrypt(
            encrypted.encode()
        )
        with pytest.raises(InvalidToken):
            Fernet(old_key.get_secret_value().encode()).decrypt(encrypted.encode())
        assert (
            conn.scalar(text("SELECT provider_session_id FROM medlm_auth.web_sessions"))
            == provider.sid
        )
        conn.execute(
            text("UPDATE medlm_auth.web_sessions SET expires_at=now()-interval '1 second'")
        )
    with pytest.raises(AppError) as error:
        app.state.auth.web(cookie)
    assert error.value.status == 401


def test_owner_context_and_mixed_credentials(auth_env):
    engine, _, provider, app = auth_env
    cookie, _, _ = sign_in(app)
    other = uuid4()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO medlm.users(id) VALUES (:id)"), {"id": other})
        conn.execute(text("INSERT INTO medlm.profiles(user_id) VALUES (:id)"), {"id": other})

    @app.get("/test-owner")
    def owner(conn=Depends(owned_connection)):
        return [
            str(value)
            for value in conn.execute(text("SELECT user_id FROM medlm.profiles")).scalars()
        ]

    with TestClient(app) as client:
        client.cookies.set("medlm_session", cookie)
        assert client.get("/test-owner").json() == [str(provider.user)]
        assert (
            client.get(
                "/api/v1/auth/session", headers={"Authorization": "Bearer synthetic-access"}
            ).status_code
            == 400
        )
        assert client.get("/api/v1/uploads").status_code == 404
        assert client.post("/api/v1/analyses", json={}).status_code == 404
        client.cookies.clear()
        assert client.get("/test-owner").status_code == 401
        with app.state.database.transaction() as conn:
            assert conn.scalar(text("SELECT count(*) FROM medlm.profiles")) == 0


def test_shared_throttle_concurrency_and_maintenance(auth_env):
    engine, settings, provider, app = auth_env
    cookie, csrf, _ = sign_in(app)
    app.state.auth.logout_web(cookie, csrf)
    limiters = [AuthRateLimiter(settings, app.state.database) for _ in range(2)]

    def hit(index):
        try:
            limiters[index % 2].check("synthetic-address")
            return 200
        except AppError as error:
            return error.status

    with ThreadPoolExecutor(5) as pool:
        results = list(pool.map(hit, range(20)))
    assert results.count(200) == 10 and results.count(429) == 10
    with engine.begin() as conn:
        key = conn.scalar(text("SELECT key_hash FROM medlm_auth.auth_throttles"))
        assert len(key) == 64 and "synthetic" not in key
        conn.execute(
            text("UPDATE medlm_auth.auth_throttles SET window_end=now()-interval '1 second'")
        )
        conn.execute(
            text("UPDATE medlm_auth.web_sessions SET expires_at=now()-interval '1 second'")
        )
        conn.execute(
            text("UPDATE medlm_auth.revoked_sessions SET expires_at=now()-interval '1 hour'")
        )
    assert cleanup(app.state.database, 1) == {"web_sessions": 1, "auth_throttles": 1}
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM medlm_auth.revoked_sessions")) == 1
    with pytest.raises(AppError):
        app.state.auth.native("synthetic-access")
    limiters[0].check("synthetic-address")


def test_corrupt_session_and_disabled_account(auth_env):
    engine, _, _, app = auth_env
    cookie, _, _ = sign_in(app)
    with engine.begin() as conn:
        conn.execute(text("UPDATE medlm.users SET disabled_at=now()"))
    with pytest.raises(AppError):
        app.state.auth.web(cookie)
    with engine.begin() as conn:
        conn.execute(text("UPDATE medlm.users SET disabled_at=NULL"))
    # New provider session for an independent corrupt-payload test.
    app.state.auth.gateway.sid = uuid4()
    cookie, _, _ = sign_in(app)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE medlm_auth.web_sessions SET encrypted_tokens='corrupt' WHERE id_hash=:id"),
            {"id": digest(cookie)},
        )
    with pytest.raises(AppError) as error:
        app.state.auth.web(cookie)
    assert error.value.status == 401


def test_provider_malformed_responses_and_key_configuration():
    for body in (b"not-json", b"[]"):
        settings = Settings(
            _env_file=None,
            supabase_url="https://auth.example.org",
            supabase_publishable_key="public-test",
        )
        gateway = SupabaseGateway(
            settings,
            httpx.Client(
                transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body))
            ),
        )
        with pytest.raises(AppError) as error:
            gateway.login("person@example.org", "synthetic-password")
        assert error.value.status == 503
        gateway.close()
    with pytest.raises(ValidationError):
        Settings(_env_file=None, session_encryption_key="invalid-key")


def test_throttling_is_shared_by_api_instances_and_db_failure_is_closed(auth_env, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError

    _, settings, provider, first = auth_env
    second = create_app(settings, provider)
    headers = {"Origin": "http://localhost:8080"}
    body = {"email": "person@example.org", "password": "synthetic-password"}
    with TestClient(first) as a, TestClient(second) as b:
        for i in range(10):
            assert (a if i % 2 else b).post(
                "/api/v1/auth/register", json=body, headers=headers
            ).status_code == 202
        denied = a.post("/api/v1/auth/register", json=body, headers=headers)
        assert denied.status_code == 429 and denied.headers["retry-after"] == "60"

        def unavailable(*args, **kwargs):
            raise SQLAlchemyError("synthetic private connection detail")

        monkeypatch.setattr(first.state.database, "transaction", unavailable)
        failed = a.post("/api/v1/auth/register", json=body, headers=headers)
        assert failed.status_code == 503
        assert "private connection" not in failed.text


def test_native_logout_outage_and_expired_web_cookie_cleanup(auth_env):
    engine, _, provider, app = auth_env
    cookie, csrf, _ = sign_in(app)
    provider.offline = True
    app.state.auth.logout_native("synthetic-access")
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT revoked_at IS NOT NULL FROM medlm_auth.web_sessions"))
    # A new, independently expired browser session returns 401 and clears its cookie.
    provider.sid, provider.offline = uuid4(), False
    cookie, _, _ = sign_in(app)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE medlm_auth.web_sessions SET expires_at=now()-interval '1 second'")
        )
    with TestClient(app) as client:
        client.cookies.set("medlm_session", cookie)
        response = client.get("/api/v1/auth/session")
        assert response.status_code == 401
        assert "Max-Age=0" in response.headers["set-cookie"]


@pytest.mark.parametrize("payload", [{}, {"access_token": 10, "refresh_token": "synthetic"}])
def test_invalid_token_responses_fail_safely(auth_env, payload):
    _, _, provider, app = auth_env
    provider.login = lambda *args: payload
    with pytest.raises(AppError) as error:
        sign_in(app)
    assert error.value.status == 503


def test_absolute_expiry_is_rechecked_after_provider_wait(auth_env, monkeypatch):
    import medlm_api.auth as auth_module

    _, _, provider, app = auth_env
    cookie, _, _ = sign_in(app)
    clock = [datetime.now(UTC)]

    class Clock:
        @staticmethod
        def now(zone):
            return clock[0]

    original = provider.verify

    def slow_verify(token):
        principal = original(token)
        clock[0] += timedelta(days=2)
        return principal

    monkeypatch.setattr(auth_module, "datetime", Clock)
    provider.verify = slow_verify
    with pytest.raises(AppError) as error:
        app.state.auth.web(cookie)
    assert error.value.status == 401

import io
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from medlm_api.auth import SupabaseGateway
from medlm_api.config import Settings
from medlm_api.errors import AppError
from medlm_api.images import MemoryTemporaryStorage, UploadRequest, validate_image
from medlm_api.main import create_app
from PIL import Image
from pydantic import ValidationError


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        environment="test",
        database_url=None,
        supabase_url=None,
        supabase_publishable_key=None,
    )


def test_health_and_future_routes(settings):
    with TestClient(create_app(settings)) as client:
        for path in ("/health", "/api/v1/health"):
            result = client.get(path)
            assert result.json() == {"status": "ok", "service": "medlm-api", "version": "0.1.0"}
            assert result.headers["cache-control"] == "no-store"
            assert result.headers["x-request-id"]
        assert client.get("/api/v1/medicines").status_code == 404
        assert client.get("/api/v1/auth/session").status_code == 401
        assert client.get("/api/v1/health/database").status_code == 401


def test_config_rejects_insecure_production_and_wildcard():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins=["*"])
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins=["https://example.org/path"])


def test_validation_never_echoes_password_or_input(settings):
    with TestClient(create_app(settings)) as client:
        secret = "sensitive-input-not-a-real-password"
        result = client.post(
            "/api/v1/auth/login",
            headers={"Origin": "http://localhost:8080"},
            json={"email": secret, "password": secret},
        )
        assert result.status_code == 422
        assert secret not in result.text
        assert result.json()["error"]["field_errors"]


def test_auth_missing_config_origin_and_rate_limit(settings):
    with TestClient(create_app(settings)) as client:
        body = {"email": "person@example.org", "password": "synthetic-test-password"}
        assert client.post("/api/v1/auth/register", json=body).status_code == 403
        headers = {"Origin": "http://localhost:8080"}
        result = client.post("/api/v1/auth/register", json=body, headers=headers)
        assert result.status_code == 503
        assert result.json()["error"]["code"] == "not_configured"
        for _ in range(9):
            client.post("/api/v1/auth/register", json=body, headers=headers)
        assert client.post("/api/v1/auth/register", json=body, headers=headers).status_code == 429
        preflight = client.options(
            "/api/v1/health",
            headers={"Origin": "https://untrusted.invalid", "Access-Control-Request-Method": "GET"},
        )
        assert "access-control-allow-origin" not in preflight.headers


def test_provider_verifies_signed_token_and_rejects_wrong_audience():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    user, session = uuid4(), uuid4()
    settings = Settings(
        _env_file=None,
        environment="test",
        supabase_url="https://auth.example.org",
        supabase_publishable_key="public-test-identifier",
    )
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"id": str(user)}))
    provider = SupabaseGateway(settings, httpx.Client(transport=transport))

    class Keys:
        def get_signing_key_from_jwt(self, token):
            class Key:
                pass

            result = Key()
            result.key = key.public_key()
            return result

    provider.jwks = Keys()
    claims = {
        "sub": str(user),
        "session_id": str(session),
        "aud": "authenticated",
        "iss": "https://auth.example.org/auth/v1",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    token = jwt.encode(claims, key, algorithm="RS256")
    assert provider.verify(token).user_id == user
    for changed in (
        {"aud": "another-app"},
        {"exp": datetime.now(UTC) - timedelta(minutes=1)},
        {"iss": "https://attacker.invalid"},
    ):
        with pytest.raises(AppError) as error:
            provider.verify(jwt.encode({**claims, **changed}, key, algorithm="RS256"))
        assert error.value.status == 401
    with pytest.raises(AppError):
        provider.verify(token + "tampered")
    provider.close()


def test_provider_masks_upstream_error():
    s = Settings(
        _env_file=None,
        environment="test",
        supabase_url="https://auth.example.org",
        supabase_publishable_key="public-test-identifier",
    )
    provider = SupabaseGateway(
        s,
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(400, json={"error": "private upstream detail"})
            )
        ),
    )
    with pytest.raises(AppError) as error:
        provider.login("person@example.org", "synthetic-test-password")
    assert "private" not in error.value.message
    provider.close()


def image_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, "PNG")
    return buffer.getvalue()


def test_image_validation_and_metadata_boundary():
    data = image_bytes()
    clean = validate_image(data, "image/png", 1024, 100)
    assert Image.open(io.BytesIO(clean)).size == (8, 8)
    for value, mime, limit, pixels, status in [
        (data, "image/jpeg", 1024, 100, 422),
        (data, "image/png", 5, 100, 413),
        (data, "image/png", 1024, 10, 422),
        (b"not an image", "image/png", 1024, 100, 422),
        (data, "image/svg+xml", 1024, 100, 415),
    ]:
        with pytest.raises(AppError) as error:
            validate_image(value, mime, limit, pixels)
        assert error.value.status == status
    with pytest.raises(ValidationError):
        UploadRequest(content_type="image/png", byte_size=20_000_000, document_kind="strip")


def test_temporary_storage_ownership_expiry_capacity_deletion():
    now = [0.0]
    store = MemoryTemporaryStorage(ttl_seconds=5, max_total_bytes=8, clock=lambda: now[0])
    owner, stranger = uuid4(), uuid4()
    key = store.put(owner, b"1234")
    with pytest.raises(AppError):
        store.read(stranger, key)
    with pytest.raises(AppError):
        store.delete(stranger, key)
    with pytest.raises(AppError):
        store.put(owner, b"12345")
    assert store.read(owner, key) == b"1234"
    now[0] = 5
    assert store.purge_expired() == 1
    with pytest.raises(AppError):
        store.read(owner, key)
    key = store.put(owner, b"1234")
    store.delete(owner, key)
    with pytest.raises(AppError):
        store.read(owner, key)

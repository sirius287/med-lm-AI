import json
import logging

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from medlm_api.config import Settings
from medlm_api.diagnostics import configuration_issues, log_configuration
from medlm_api.main import create_app
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch):
    for name in Settings.model_fields:
        monkeypatch.delenv("MEDLM_" + name.upper(), raising=False)


def empty(**values):
    return Settings(_env_file=None, environment="test", **values)


def test_missing_configuration_is_actionable_and_never_requires_ai():
    issues = configuration_issues(empty())
    names = {name for issue in issues for name in issue.variables}
    assert "MEDLM_DATABASE_URL" in names
    assert "MEDLM_SESSION_ENCRYPTION_KEY" in names
    assert "MEDLM_MEDICATION_ENCRYPTION_KEY" in names
    assert not any("OPENAI" in name for name in names)


def test_diagnostics_never_log_values(caplog):
    key = Fernet.generate_key().decode()
    private = "not-a-real-provider-publishable-key"
    settings = empty(
        session_encryption_key=key, medication_encryption_key=key, supabase_publishable_key=private
    )
    with caplog.at_level(logging.WARNING):
        log_configuration(settings, logging.getLogger("diagnostic-test"))
    assert key not in caplog.text and private not in caplog.text
    assert any(i.code == "encryption_keys_must_differ" for i in configuration_issues(settings))
    for record in caplog.records:
        assert set(json.loads(record.message)) == {"event", "code", "variables", "capability"}


def test_dotenv_empty_placeholders_and_environment_priority(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("MEDLM_DATABASE_URL=\nMEDLM_SESSION_ENCRYPTION_KEY=\nMEDLM_VERSION=file\n")
    monkeypatch.setenv("MEDLM_VERSION", "environment")
    settings = Settings(_env_file=path)
    assert settings.database_url is None and settings.session_encryption_key is None
    assert settings.version == "environment"


def test_startup_diagnostics_preserve_liveness_and_fail_closed(caplog):
    with TestClient(create_app(empty())) as client:
        assert client.get("/health").status_code == 200
        assert (
            client.get("/api/v1/auth/session").json()["error"]["code"] == "authentication_required"
        )
        assert client.get("/api/v1/diagnostics").status_code == 404
        assert client.get("/api/v1/analyses").status_code == 404
    assert "MEDLM_DATABASE_URL" in caplog.text


def test_original_503_causes_are_separate_and_no_provider_request_occurs():
    import httpx
    from medlm_api.auth import SupabaseGateway

    def no_network(request):
        raise AssertionError("Missing configuration must fail before network access")

    settings = empty()
    gateway = SupabaseGateway(settings, httpx.Client(transport=httpx.MockTransport(no_network)))
    body = {"email": "person@example.org", "password": "synthetic-test-password"}
    with TestClient(create_app(settings, gateway)) as client:
        for operation, component in (
            ("register", "Supabase Auth"),
            ("login", "Session encryption"),
        ):
            response = client.post(
                "/api/v1/auth/" + operation, json=body, headers={"Origin": "http://localhost:8080"}
            )
            assert response.status_code == 503
            assert response.json()["error"]["code"] == "not_configured"
            assert response.json()["error"]["message"] == component + " is not configured."


def test_production_requires_separate_medication_encryption_and_masks_invalid_input():
    session = Fernet.generate_key().decode()
    values = dict(
        _env_file=None,
        environment="production",
        cookie_secure=True,
        cors_origins=["https://app.example.org"],
        database_url="postgresql+psycopg://runtime:synthetic@db.invalid/medlm",
        supabase_url="https://auth.example.org",
        supabase_publishable_key="public-test-identifier",
        auth_rate_limit_key="synthetic-rate-limit-identifier-long-enough",
        session_encryption_key=session,
    )
    for key in (None, session):
        with pytest.raises(ValidationError):
            Settings(**values, medication_encryption_key=key)
    Settings(**values, medication_encryption_key=Fernet.generate_key().decode())
    private = "malformed-synthetic-key-must-never-be-logged"
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, session_encryption_key=private)
    assert private not in str(error.value)

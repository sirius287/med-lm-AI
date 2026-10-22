"""Provider failures are actionable for operators without recording account data."""

import json
import logging
from contextlib import contextmanager

import httpx
import pytest
from fastapi.testclient import TestClient
from medlm_api.auth import SupabaseGateway
from medlm_api.config import Settings
from medlm_api.errors import AppError
from medlm_api.main import create_app

PRIVATE = "synthetic-private-value-must-not-be-logged"
EMAIL = "person@example.org"


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch):
    for name in Settings.model_fields:
        monkeypatch.delenv("MEDLM_" + name.upper(), raising=False)


@contextmanager
def gateway(handler):
    settings = Settings(
        _env_file=None,
        environment="test",
        supabase_url="https://auth.example.org",
        supabase_publishable_key=PRIVATE,
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        yield SupabaseGateway(settings, client)


def diagnostic(caplog):
    records = [r for r in caplog.records if r.name == "medlm.auth"]
    assert len(records) == 1
    record = records[0]
    assert record.exc_info is None and record.stack_info is None
    assert PRIVATE not in caplog.text and EMAIL not in caplog.text
    value = json.loads(record.getMessage())
    assert set(value) == {"event", "operation", "reason", "upstream_status", "provider_code"}
    assert value["event"] == "auth_provider_unavailable"
    return value


@pytest.mark.parametrize(
    "status,body,code",
    [
        (429, {"code": "over_email_send_rate_limit"}, "over_email_send_rate_limit"),
        (429, {"error_code": "over_request_rate_limit"}, "over_request_rate_limit"),
        (500, {"code": 500, "error_code": "unexpected_failure"}, "unexpected_failure"),
        (503, {"code": PRIVATE}, "unclassified"),
        (502, {"code": {"private": PRIVATE}}, "unclassified"),
        (500, {"code": "unexpected_failure\n" + PRIVATE}, "unclassified"),
    ],
)
def test_provider_http_failure_logs_only_allowlisted_metadata(caplog, status, body, code):
    with gateway(lambda _: httpx.Response(status, json={**body, "message": PRIVATE})) as provider:
        with (
            caplog.at_level(logging.WARNING, logger="medlm.auth"),
            pytest.raises(AppError) as error,
        ):
            provider.register(EMAIL, PRIVATE)
    assert (error.value.status, error.value.code, error.value.retryable) == (
        503,
        "auth_unavailable",
        True,
    )
    assert PRIVATE not in error.value.message
    assert diagnostic(caplog) == {
        "event": "auth_provider_unavailable",
        "operation": "registration",
        "reason": "upstream_error",
        "upstream_status": status,
        "provider_code": code,
    }


@pytest.mark.parametrize("failure", [httpx.ConnectError, httpx.ReadTimeout])
def test_transport_error_never_logs_exception_or_request(caplog, failure):
    def fail(request):
        raise failure(PRIVATE, request=request)

    with gateway(fail) as provider:
        with (
            caplog.at_level(logging.WARNING, logger="medlm.auth"),
            pytest.raises(AppError) as error,
        ):
            provider.register(EMAIL, PRIVATE)
    assert error.value.code == "auth_unavailable"
    assert diagnostic(caplog) == {
        "event": "auth_provider_unavailable",
        "operation": "registration",
        "reason": "transport_error",
        "upstream_status": None,
        "provider_code": "unclassified",
    }


@pytest.mark.parametrize(
    "response,reason",
    [
        (
            httpx.Response(302, headers={"Location": "https://private.invalid/" + PRIVATE}),
            "unexpected_redirect",
        ),
        (httpx.Response(200, content=PRIVATE), "invalid_response"),
        (httpx.Response(200, json=[PRIVATE]), "invalid_response"),
        (httpx.Response(503, content=PRIVATE), "upstream_error"),
    ],
)
def test_malformed_and_redirect_responses_log_no_raw_content(caplog, response, reason):
    with gateway(lambda _: response) as provider:
        with (
            caplog.at_level(logging.WARNING, logger="medlm.auth"),
            pytest.raises(AppError) as error,
        ):
            provider.register(EMAIL, PRIVATE)
    assert error.value.code == "auth_unavailable"
    value = diagnostic(caplog)
    assert value["reason"] == reason
    assert value["upstream_status"] == response.status_code
    assert value["provider_code"] == "unclassified"
    assert "private.invalid" not in caplog.text


def test_unknown_internal_operation_is_not_logged_as_a_raw_path(caplog):
    with gateway(lambda _: httpx.Response(503)) as provider:
        with caplog.at_level(logging.WARNING, logger="medlm.auth"), pytest.raises(AppError):
            provider._request("GET", "unknown?private=" + PRIVATE, token=PRIVATE)
    assert diagnostic(caplog)["operation"] == "other"


@pytest.mark.parametrize("status", [200, 400])
def test_success_and_credentials_rejection_keep_existing_behavior_without_diagnostics(
    caplog, status
):
    with gateway(lambda _: httpx.Response(status, json={"message": PRIVATE})) as provider:
        with caplog.at_level(logging.WARNING, logger="medlm.auth"):
            if status == 200:
                provider.register(EMAIL, PRIVATE)
            else:
                with pytest.raises(AppError) as error:
                    provider.login(EMAIL, PRIVATE)
                assert (error.value.status, error.value.code) == (401, "authentication_failed")
                assert PRIVATE not in error.value.message
    assert not [r for r in caplog.records if r.name == "medlm.auth"]


def test_public_registration_error_stays_generic_and_safe(caplog):
    response = httpx.Response(
        429, json={"error_code": "over_email_send_rate_limit", "message": PRIVATE}
    )
    with gateway(lambda _: response) as provider:
        with TestClient(create_app(provider.settings, provider)) as client:
            result = client.post(
                "/api/v1/auth/register",
                headers={"Origin": "http://localhost:8080"},
                json={"email": EMAIL, "password": PRIVATE},
            )
    assert result.status_code == 503
    assert result.json()["error"] == {
        "code": "auth_unavailable",
        "message": "Authentication is unavailable.",
        "retryable": True,
        "field_errors": [],
    }
    assert "over_email_send_rate_limit" not in result.text
    assert PRIVATE not in result.text and EMAIL not in result.text
    assert diagnostic(caplog)["provider_code"] == "over_email_send_rate_limit"

from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from dotenv import dotenv_values
from medlm_api.config import Settings
from medlm_api.development import (
    SetupRefused,
    database_url,
    local_url,
    new_environment,
    read_private_environment,
    refuse_existing,
    write_environment,
)


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch):
    for name in Settings.model_fields:
        monkeypatch.delenv("MEDLM_" + name.upper(), raising=False)


def test_target_guard_rejects_other_projects_servers_roles_and_url_options():
    valid = database_url("medlm_runtime", "synthetic-password")
    assert local_url(valid, "medlm_runtime") == valid
    for value in (
        valid.set(host="db.example.org"),
        valid.set(database="ninecgpa_dev"),
        valid.set(database="urjavolt_db"),
        valid.set(database="postgres"),
        valid.set(username="postgres"),
        valid.set(port=15432),
        valid.update_query_dict({"options": "-c role=postgres"}),
        "not-a-url",
    ):
        with pytest.raises(SetupRefused):
            local_url(value, "medlm_runtime")


@pytest.mark.parametrize(
    "names,roles",
    [
        ({"medlm_dev"}, set()),
        (set(), {"medlm_owner"}),
        (set(), {"medlm_runtime"}),
    ],
)
def test_initialization_refuses_preexisting_resources(names, roles):
    with pytest.raises(SetupRefused):
        refuse_existing(names, roles)


def test_environment_has_distinct_stable_keys_and_runtime_only(tmp_path):
    path = tmp_path / ".env"
    url = database_url("medlm_runtime", "synthetic-password#with-reserved-chars")
    values = new_environment(url.render_as_string(hide_password=False))
    write_environment(path, values)
    before = path.read_bytes()
    settings = Settings(_env_file=path)
    assert settings.database_url.get_secret_value() == values["MEDLM_DATABASE_URL"]
    assert "medlm_owner" not in before.decode()
    assert settings.session_encryption_key != settings.medication_encryption_key
    for field in (settings.session_encryption_key, settings.medication_encryption_key):
        cipher = Fernet(field.get_secret_value().encode())
        assert cipher.decrypt(cipher.encrypt(b"synthetic")) == b"synthetic"
    assert len(settings.auth_rate_limit_key.get_secret_value()) >= 32
    assert read_private_environment(path)["MEDLM_DATABASE_URL"] == values["MEDLM_DATABASE_URL"]
    with pytest.raises(SetupRefused):
        write_environment(path, new_environment(url.render_as_string(hide_password=False)))
    assert path.read_bytes() == before


def test_environment_rejects_line_injection_without_writing(tmp_path):
    path = tmp_path / ".env"
    with pytest.raises(SetupRefused):
        write_environment(path, {"MEDLM_SUPABASE_URL": "https://example.org\nEVIL=yes"})
    assert not path.exists()


def test_compatibility_template_has_the_same_safe_configuration_as_example():
    root = Path(__file__).resolve().parents[3]
    example = dotenv_values(root / ".env.example")
    assert example == dotenv_values(root / "config/backend.env.template")
    for name in (
        "MEDLM_DATABASE_URL",
        "MEDLM_SESSION_ENCRYPTION_KEY",
        "MEDLM_MEDICATION_ENCRYPTION_KEY",
        "MEDLM_SUPABASE_PUBLISHABLE_KEY",
        "MEDLM_AUTH_RATE_LIMIT_KEY",
    ):
        assert not example[name]

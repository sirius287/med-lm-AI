"""Guardrails shared by the local development CLI and offline tests."""

import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import dotenv_values
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError


class SetupRefused(ValueError):
    """Safe operator message; must not contain setting values."""


def local_url(value, role, *, port=5432):
    try:
        url = make_url(value)
    except (ArgumentError, TypeError, ValueError) as exc:
        # Parsing an operator-supplied connection string is the only boundary here.
        raise SetupRefused("Invalid database URL; no connection was attempted.") from exc
    if (
        url.drivername != "postgresql+psycopg"
        or url.host != "127.0.0.1"
        or url.port != port
        or url.database != "medlm_dev"
        or url.username != role
        or url.query
        or not url.password
    ):
        raise SetupRefused("Expected only the named MedLM role on 127.0.0.1:5432/medlm_dev.")
    return url


def refuse_existing(names, roles):
    if "medlm_dev" in names or {"medlm_owner", "medlm_runtime"}.intersection(roles):
        raise SetupRefused(
            "MedLM database or roles already exist. Nothing was changed; inspect manually."
        )


def new_environment(runtime_url, *, port=5432):
    local_url(runtime_url, "medlm_runtime", port=port)
    return {
        "MEDLM_ENVIRONMENT": "development",
        "MEDLM_DATABASE_URL": runtime_url,
        "MEDLM_SESSION_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "MEDLM_MEDICATION_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "MEDLM_AUTH_RATE_LIMIT_KEY": secrets.token_urlsafe(48),
        "MEDLM_SESSION_DECRYPTION_KEYS": "[]",
        "MEDLM_CORS_ORIGINS": '["http://localhost:8080","http://127.0.0.1:8080"]',
        "MEDLM_COOKIE_SECURE": "false",
    }


def write_environment(path: Path, values):
    # Exclusive creation: keys are stable, never silently rotated or overwritten.
    def quoted(value):
        if "\n" in value or "\r" in value or "'" in value or "\\" in value:
            raise SetupRefused("Unsupported configuration characters; no file was written.")
        return "'" + value + "'"

    content = "# Private local settings. Never commit or share this file.\n"
    content += "".join(f"{key}={quoted(value)}\n" for key, value in values.items())
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise SetupRefused(".env already exists; refusing to overwrite keys or settings.") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
        file.write(content)


def read_private_environment(path):
    return dotenv_values(path, interpolate=False)


def verify_runtime(conn, *, port=5432):
    """Read-only checks, executed through the actual runtime login."""
    identity = conn.execute(
        text(
            "SELECT current_database(), current_user, host(inet_server_addr()), inet_server_port()"
        )
    ).one()
    if tuple(identity) != ("medlm_dev", "medlm_runtime", "127.0.0.1", port):
        raise SetupRefused("Runtime target identity mismatch.")
    attributes = conn.execute(
        text(
            "SELECT rolsuper,rolcreatedb,rolcreaterole,rolbypassrls,rolreplication "
            "FROM pg_roles WHERE rolname=current_user"
        )
    ).one()
    if any(attributes):
        raise SetupRefused("Runtime has unsafe administrative privileges.")
    if conn.scalar(
        text(
            "SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles "
            "WHERE rolname=current_user)"
        )
    ):
        raise SetupRefused("Runtime must not inherit another role.")
    # Runtime deliberately has no alembic_version access; owner verifies the head separately.
    for table in ("medications", "medication_schedules", "dose_occurrences", "dose_events"):
        if not conn.scalar(
            text("SELECT has_table_privilege(current_user,:table,'SELECT')"),
            {"table": "medlm." + table},
        ):
            raise SetupRefused("Manual medication runtime grants are incomplete.")
    for table in ("uploads", "medicine_analyses", "prescriptions", "verification_sources"):
        if conn.scalar(
            text("SELECT has_table_privilege(current_user,:table,'SELECT')"),
            {"table": "medlm." + table},
        ):
            raise SetupRefused("Normal runtime unexpectedly has clinical/synthetic access.")
    if conn.scalar(
        text(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname IN ('medlm','medlm_auth') AND c.relkind='r' "
            "AND c.relowner=(SELECT oid FROM pg_roles WHERE rolname=current_user)"
        )
    ):
        raise SetupRefused("Runtime must not own application tables.")
    for table in ("medications", "profiles", "users"):
        if not conn.scalar(
            text(
                "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class "
                "WHERE oid=to_regclass(:table)"
            ),
            {"table": "medlm." + table},
        ):
            raise SetupRefused("Required FORCE RLS is absent.")


def database_url(role, password, database="medlm_dev", *, port=5432):
    return URL.create(
        "postgresql+psycopg",
        username=role,
        password=password,
        host="127.0.0.1",
        port=port,
        database=database,
    )

"""Guarded local MedLM setup. Passwords are entered privately, never as CLI arguments."""

import argparse
import getpass
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api"))

import psycopg  # noqa: E402
from alembic.config import Config  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
from medlm_api.config import Settings  # noqa: E402
from medlm_api.development import (  # noqa: E402
    SetupRefused,
    database_url,
    local_url,
    new_environment,
    read_private_environment,
    refuse_existing,
    verify_runtime,
    write_environment,
)
from medlm_api.diagnostics import configuration_issues  # noqa: E402
from psycopg import sql  # noqa: E402
from pydantic import ValidationError  # noqa: E402
from pydantic_settings import SettingsError  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402


def private_password(label):
    value = getpass.getpass(label + ": ")
    if len(value) < 16:
        raise SetupRefused("Use a unique password of at least 16 characters.")
    if value != getpass.getpass("Confirm " + label + ": "):
        raise SetupRefused("Passwords differ; nothing was changed.")
    return value


def initialize(*, port=5432, environment_path=None):
    # Test-only injection seams: the CLI accepts no target/port/path override.
    environment_path = environment_path or ROOT / ".env"
    if environment_path.exists() or os.getenv("MEDLM_DATABASE_URL"):
        raise SetupRefused(
            "Existing .env or process database URL: inspect it before initialization."
        )
    admin = getpass.getpass("Local PostgreSQL postgres password (not saved): ")
    owner = private_password("New medlm_owner password (save privately for future migrations)")
    runtime = private_password("New medlm_runtime password")
    if owner == runtime:
        raise SetupRefused("Owner and runtime passwords must differ.")
    print(f"Preflight target: 127.0.0.1:{port}, database postgres, role postgres.")
    # Only catalogs are read until the exact local identity and absence checks succeed.
    with psycopg.connect(
        host="127.0.0.1",
        port=port,
        dbname="postgres",
        user="postgres",
        password=admin,
        connect_timeout=5,
        autocommit=True,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT current_database(),current_user,host(inet_server_addr()),inet_server_port()"
            )
            if cur.fetchone() != ("postgres", "postgres", "127.0.0.1", port):
                raise SetupRefused("Administrator target identity mismatch.")
            cur.execute("SELECT datname FROM pg_database WHERE datname='medlm_dev'")
            names = {row[0] for row in cur.fetchall()}
            cur.execute(
                "SELECT rolname FROM pg_roles WHERE rolname IN ('medlm_owner','medlm_runtime')"
            )
            refuse_existing(names, {row[0] for row in cur.fetchall()})
            print(
                "Verified: MedLM database and roles are absent. Creating only named MedLM resources."
            )
            for role, password in (("medlm_owner", owner), ("medlm_runtime", runtime)):
                # Send only a SCRAM verifier in DDL, never a plaintext role password.
                verifier = conn.pgconn.encrypt_password(
                    password.encode("utf-8"), role.encode("utf-8"), b"scram-sha-256"
                ).decode("ascii")
                cur.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                        "NOREPLICATION NOBYPASSRLS PASSWORD {}"
                    ).format(sql.Identifier(role), sql.Literal(verifier))
                )
            cur.execute("CREATE DATABASE medlm_dev OWNER medlm_owner TEMPLATE template0")
            cur.execute("REVOKE CONNECT, TEMPORARY ON DATABASE medlm_dev FROM PUBLIC")
            cur.execute("GRANT CONNECT ON DATABASE medlm_dev TO medlm_owner,medlm_runtime")
    with psycopg.connect(
        host="127.0.0.1",
        port=port,
        dbname="medlm_dev",
        user="medlm_owner",
        password=owner,
        connect_timeout=5,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT current_database(),current_user,host(inet_server_addr()),inet_server_port()"
            )
            if cur.fetchone() != ("medlm_dev", "medlm_owner", "127.0.0.1", port):
                raise SetupRefused("Owner target identity mismatch.")
            cur.execute(
                "SELECT count(*) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema')"
            )
            if cur.fetchone()[0]:
                raise SetupRefused("New database is not empty. No migrations were applied.")
    env = {k: v for k, v in os.environ.items() if not k.startswith("MEDLM_")}
    env["MEDLM_ENVIRONMENT"] = "development"
    env["MEDLM_DATABASE_URL"] = database_url("medlm_owner", owner, port=port).render_as_string(
        hide_password=False
    )
    env["PYTHONPATH"] = str(ROOT / "services/api")
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=env,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    expected = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini"))).get_current_head()
    with psycopg.connect(
        host="127.0.0.1", port=port, dbname="medlm_dev", user="medlm_owner", password=owner
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version_num FROM alembic_version")
            if cur.fetchone()[0] != expected:
                raise SetupRefused("Migration head mismatch; no grants were applied.")
            cur.execute((ROOT / "database/runtime_grants.sql").read_text())
    runtime_url = database_url("medlm_runtime", runtime, port=port)
    engine = create_engine(runtime_url, hide_parameters=True, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as conn:
            verify_runtime(conn, port=port)
    finally:
        engine.dispose()
    write_environment(
        environment_path,
        new_environment(runtime_url.render_as_string(hide_password=False), port=port),
    )
    print("Local database initialized and restricted runtime verified. Private .env created.")
    print("Owner password was not saved. Keep it in your private password manager.")
    print("Next: uv run python scripts/dev.py configure-auth")


def configure_auth():
    path = ROOT / ".env"
    if not path.is_file():
        raise SetupRefused("Initialize the isolated database first.")
    values = read_private_environment(path)
    local_url(values.get("MEDLM_DATABASE_URL", ""), "medlm_runtime")
    if any(values.get(key) for key in ("MEDLM_SUPABASE_URL", "MEDLM_SUPABASE_PUBLISHABLE_KEY")):
        raise SetupRefused(
            "Auth configuration already exists; inspect privately rather than overwrite it."
        )
    url = getpass.getpass("Development Supabase project URL (hidden input): ").strip()
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.path not in ("", "/")
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise SetupRefused("Expected an HTTPS project origin only.")
    key = getpass.getpass(
        "Development Supabase publishable key (not secret/service-role): "
    ).strip()
    if not key.startswith("sb_publishable_") or any(c.isspace() for c in key):
        raise SetupRefused(
            "Use the project's current sb_publishable_ key; never a secret/service-role key."
        )
    # Append only; encryption keys and existing settings remain byte-for-byte intact.
    if "'" in key or "'" in url:
        raise SetupRefused("Unsupported configuration characters.")
    with path.open("a", encoding="utf-8", newline="\n") as file:
        file.write(f"\nMEDLM_SUPABASE_URL='{url.rstrip('/')}'\n")
        file.write(f"MEDLM_SUPABASE_PUBLISHABLE_KEY='{key}'\n")
    print("Auth settings saved privately. Restart the API; no provider was contacted.")


def check(database=False):
    try:
        settings = Settings(_env_file=ROOT / ".env")
    except (ValidationError, SettingsError):
        raise SetupRefused(
            "Invalid configuration. Check variable names/formats in .env.example; values suppressed."
        ) from None
    issues = configuration_issues(settings)
    for issue in issues:
        print(json.dumps(issue.as_dict()))
    if database:
        if not settings.database_url:
            raise SetupRefused("MEDLM_DATABASE_URL is missing.")
        url = local_url(settings.database_url.get_secret_value(), "medlm_runtime")
        engine = create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 5})
        try:
            with engine.connect() as conn:
                verify_runtime(conn)
        finally:
            engine.dispose()
        print("Read-only runtime identity, grants, role restrictions and FORCE RLS checks passed.")
    print("Configuration checked; live provider connectivity/sign-in has NOT been tested.")
    return 1 if issues else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "init-db", "configure-auth"))
    parser.add_argument(
        "--database", action="store_true", help="Also check the exact local runtime, read-only"
    )
    args = parser.parse_args()
    os.chdir(ROOT)
    try:
        if args.command == "init-db":
            initialize()
        elif args.command == "configure-auth":
            configure_auth()
        else:
            return check(args.database)
    except SetupRefused as exc:
        print("REFUSED: " + str(exc), file=sys.stderr)
        return 1
    except (psycopg.Error, SQLAlchemyError, subprocess.CalledProcessError):
        print(
            "Setup failed. Error details suppressed to protect credentials. Resources are never dropped; inspect locally before retrying.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

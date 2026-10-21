"""Run PostgreSQL tests in a NEW private cluster; never connect to an existing service.

Requires installed PostgreSQL binaries. No downloaded server, shared database,
pre-existing URL, trust authentication or production secret is used.
"""

import argparse
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[1]


def binaries(directory):
    suffix = ".exe" if os.name == "nt" else ""
    result = {}
    for name in ("initdb", "pg_ctl"):
        path = Path(directory) / (name + suffix) if directory else shutil.which(name)
        if not path or not Path(path).is_file():
            raise RuntimeError(
                "PostgreSQL binaries missing; provide --pg-bin (see SETUP_WINDOWS.md)"
            )
        result[name] = str(path)
    return result


def setup_smoke(work, port, password, env):
    sys.path.insert(0, str(ROOT / "scripts"))
    import dev
    from dotenv import dotenv_values

    owner, runtime = secrets.token_urlsafe(30), secrets.token_urlsafe(30)
    destination = work / ".env"
    original = ROOT / ".env"
    before = original.read_bytes() if original.exists() else None
    with patch.dict(os.environ, env, clear=True):
        with patch.object(
            dev.getpass, "getpass", side_effect=[password, owner, owner, runtime, runtime]
        ):
            dev.initialize(port=port, environment_path=destination)
        values = dotenv_values(destination, interpolate=False)
        assert values["MEDLM_SESSION_ENCRYPTION_KEY"] != values["MEDLM_MEDICATION_ENCRYPTION_KEY"]
        assert "medlm_owner" not in values["MEDLM_DATABASE_URL"]
        saved = destination.read_bytes()
        try:
            dev.initialize(port=port, environment_path=destination)
        except dev.SetupRefused:
            pass
        else:
            raise AssertionError("Setup did not refuse existing settings")
        assert destination.read_bytes() == saved
    assert (original.read_bytes() if original.exists() else None) == before
    print(
        "Setup smoke passed: owner migration, real restricted runtime login/grants, "
        "separate stable keys, overwrite refusal; actual root .env unchanged.",
        flush=True,
    )


def run(pg_bin=None, pytest_args=(), *, setup_only=False):
    programs = binaries(pg_bin)
    work = ROOT / ".local" / "test-runs" / uuid4().hex
    work.mkdir(parents=True, mode=0o700)
    data = work / "data"
    password = secrets.token_urlsafe(40)
    pwfile = work / "bootstrap-password"
    descriptor = os.open(pwfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        file.write(password + "\n")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    # No inherited application/test connection string or provider configuration.
    env = {k: v for k, v in os.environ.items() if not k.startswith(("MEDLM_", "SUPABASE_", "PG"))}
    env["PYTHONPATH"] = os.pathsep.join(
        str(ROOT / p) for p in ("services/api", "packages/backend_domain")
    )
    env["MEDLM_ENVIRONMENT"] = "test"
    started = False
    engine = None
    try:
        subprocess.run(
            [
                programs["initdb"],
                "-D",
                str(data),
                "-U",
                "postgres",
                "--pwfile",
                str(pwfile),
                "-A",
                "scram-sha-256",
                "--encoding=UTF8",
                "--no-locale",
            ],
            check=True,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        pwfile.unlink()
        # Windows does not support Unix sockets; isolate Unix socket directory elsewhere too.
        options = f"-h 127.0.0.1 -p {port}"
        if os.name != "nt":
            options += f" -k {work}"
        subprocess.run(
            [
                programs["pg_ctl"],
                "start",
                "-D",
                str(data),
                "-l",
                str(work / "postgres.log"),
                "-o",
                options,
                "-w",
                "-t",
                "30",
            ],
            check=True,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        started = True
        url = URL.create(
            "postgresql+psycopg",
            username="postgres",
            password=password,
            host="127.0.0.1",
            port=port,
            database="postgres",
        )
        engine = create_engine(url, hide_parameters=True, isolation_level="AUTOCOMMIT")
        with engine.connect() as conn:
            actual = Path(conn.scalar(text("SHOW data_directory"))).resolve()
            assert actual == data.resolve(), "Wrong cluster; refusing all test writes"
            assert conn.scalar(text("SELECT current_user")) == "postgres"
            assert conn.scalar(text("SELECT inet_server_port()")) == port
            names = set(conn.execute(text("SELECT datname FROM pg_database")).scalars())
            assert names == {"postgres", "template0", "template1"}, "Cluster is not fresh"
            if not setup_only:
                conn.execute(text("CREATE DATABASE medlm_suite TEMPLATE template0"))
        if setup_only:
            setup_smoke(work, port, password, env)
            (work / "result.json").write_text(
                json.dumps({"setup_smoke": "passed", "isolated_cluster": True}) + "\n",
                encoding="utf-8",
            )
            return 0
        target = url.set(database="medlm_suite").render_as_string(hide_password=False)
        for key in (
            "MEDLM_DATABASE_URL",
            "MEDLM_TEST_DATABASE_URL",
            "MEDLM_MIGRATION_TEST_ADMIN_URL",
        ):
            env[key] = target
        # Migrations run only after data_directory, identity and freshness checks above.
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=ROOT,
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        suite = create_engine(target, hide_parameters=True)
        try:
            with suite.begin() as conn:
                conn.execute(text((ROOT / "scripts/test_role.sql").read_text()))
                conn.execute(text((ROOT / "database/runtime_grants.sql").read_text()))
        finally:
            suite.dispose()
        command = [sys.executable, "-m", "pytest", "-q", "--tb=short", *pytest_args]
        print(
            "Verified NEW loopback PostgreSQL cluster; existing services are untouched.", flush=True
        )
        print("Test command: python -m pytest -q --tb=short " + " ".join(pytest_args), flush=True)
        result = subprocess.run(
            command, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        output = result.stdout.replace(password, "[redacted-disposable-password]")
        (work / "pytest.log").write_text(output, encoding="utf-8")
        print(output, end="", flush=True)
        (work / "result.json").write_text(
            json.dumps(
                {
                    "command": ["python", "-m", "pytest", "-q", "--tb=short", *pytest_args],
                    "exit_code": result.returncode,
                    "isolated_cluster": True,
                    "cluster_directory": str(work.relative_to(ROOT)),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print("Safe result/log directory: " + str(work.relative_to(ROOT)), flush=True)
        return result.returncode
    finally:
        if engine:
            engine.dispose()
        if started:
            subprocess.run(
                [programs["pg_ctl"], "stop", "-D", str(data), "-m", "fast", "-w"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        pwfile.unlink(missing_ok=True)
        # No recursive deletion: retained cluster is ignored and contains synthetic data only.


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin", default=os.getenv("MEDLM_PG_BIN"))
    parser.add_argument(
        "--setup-only", action="store_true", help="Smoke-test guarded setup in a NEW cluster"
    )
    args, rest = parser.parse_known_args()
    raise SystemExit(run(args.pg_bin, rest, setup_only=args.setup_only))

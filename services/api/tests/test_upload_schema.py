"""Real PostgreSQL only. Creates/drops randomly named, empty disposable databases.

MEDLM_MIGRATION_TEST_ADMIN_URL must explicitly point to a disposable local cluster
with CREATE DATABASE/ROLE privileges. Never use production credentials.
"""

import os
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.database
ROOT = Path(__file__).resolve().parents[3]
HEAD = "0002_synthetic_uploads"
TABLES = (
    "uploads",
    "upload_objects",
    "upload_deletion_jobs",
    "upload_audit_events",
    "upload_deletion_receipts",
    "upload_safeguard_runs",
)


@pytest.fixture
def isolated_database(monkeypatch):
    url = os.getenv("MEDLM_MIGRATION_TEST_ADMIN_URL")
    if not url:
        pytest.skip("MEDLM_MIGRATION_TEST_ADMIN_URL not set; migration paths not validated")
    name = "medlm_schema_test_" + uuid4().hex
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    target = make_url(url).set(database=name).render_as_string(hide_password=False)
    monkeypatch.setenv("MEDLM_DATABASE_URL", target)
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "database/migrations"))
    engine = create_engine(target)
    try:
        yield engine, cfg
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE "{name}"'))
        admin.dispose()


def snapshot(conn):
    return conn.execute(
        text("""SELECT table_schema,table_name,column_name,data_type,
        is_nullable,column_default FROM information_schema.columns
        WHERE table_schema IN ('medlm','medlm_auth') ORDER BY 1,2,ordinal_position""")
    ).all()


@pytest.mark.parametrize("path", ["empty", "phase1"])
def test_migration_paths_preserve_phase1_and_reverse(isolated_database, path):
    engine, cfg = isolated_database
    baseline = None
    identity = uuid4()
    if path == "phase1":
        command.upgrade(cfg, "0001_foundation")
        with engine.begin() as conn:
            baseline = snapshot(conn)
            conn.execute(text("INSERT INTO medlm.users(id) VALUES (:id)"), {"id": identity})
            conn.execute(
                text("INSERT INTO medlm.profiles(user_id,locale) VALUES (:id,'te-IN')"),
                {"id": identity},
            )
            conn.execute(
                text("""INSERT INTO medlm_auth.revoked_sessions
                VALUES (:sid,:id,now()+interval '1 hour')"""),
                {"sid": uuid4(), "id": identity},
            )
    command.upgrade(cfg, HEAD)
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
        if baseline:
            assert [row for row in snapshot(conn) if row.table_name not in TABLES] == baseline
            assert (
                conn.scalar(
                    text("SELECT locale FROM medlm.profiles WHERE user_id=:id"), {"id": identity}
                )
                == "te-IN"
            )
            assert conn.scalar(text("SELECT count(*) FROM medlm_auth.revoked_sessions")) == 1
        for table in TABLES:
            assert conn.scalar(text(f"SELECT count(*) FROM medlm.{table}")) == 0
    command.downgrade(cfg, "0001_foundation")
    with engine.connect() as conn:
        if baseline:
            assert snapshot(conn) == baseline
            assert conn.scalar(text("SELECT count(*) FROM medlm.users")) == 1
        assert conn.scalar(text("SELECT to_regclass('medlm.uploads')")) is None
    command.upgrade(cfg, HEAD)


@pytest.fixture
def schema(isolated_database):
    engine, cfg = isolated_database
    command.upgrade(cfg, HEAD)
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            yield conn
        finally:
            transaction.rollback()


def upload(conn, user=None):
    user, identity = user or uuid4(), uuid4()
    conn.execute(
        text("INSERT INTO medlm.users(id) VALUES (:id) ON CONFLICT DO NOTHING"), {"id": user}
    )
    conn.execute(
        text("""INSERT INTO medlm.uploads
      (id,user_id,notice_version,document_kind,mime,declared_bytes,ticket_hash,ticket_expires_at,expires_at)
      VALUES (:id,:user,'synthetic-v1','box','image/png',100,:ticket,
        now()+interval '5 minutes',now()+interval '1 hour')"""),
        {"id": identity, "user": user, "ticket": uuid4().hex + uuid4().hex},
    )
    return user, identity


def object_row(conn, user, parent):
    identity = uuid4()
    conn.execute(
        text("""INSERT INTO medlm.upload_objects
      (id,user_id,upload_id,object_key,kind,expires_at) VALUES
      (:id,:user,:parent,:key,'original',now()+interval '30 minutes')"""),
        {"id": identity, "user": user, "parent": parent, "key": uuid4()},
    )
    return identity


@contextmanager
def rejected(conn):
    with pytest.raises(DBAPIError):
        with conn.begin_nested():
            yield


def test_owner_isolation_and_no_application_grants(schema):
    conn = schema
    first, parent = upload(conn)
    second, other = upload(conn)
    object_row(conn, first, parent)
    # Provision only a transaction-local test role/grants; never grants the API access.
    role = "upload_test_" + uuid4().hex
    conn.execute(text(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS'))
    conn.execute(text(f'GRANT USAGE ON SCHEMA medlm TO "{role}"'))
    for table in TABLES:
        assert not conn.scalar(
            text("SELECT has_table_privilege('medlm_runtime',:t,'SELECT')"), {"t": "medlm." + table}
        )
        conn.execute(text(f'GRANT SELECT,INSERT,UPDATE,DELETE ON medlm.{table} TO "{role}"'))
    conn.execute(text(f'SET LOCAL ROLE "{role}"'))
    assert conn.scalar(text("SELECT count(*) FROM medlm.uploads")) == 0
    conn.execute(text("SELECT set_config('app.user_id',:id,true)"), {"id": str(first)})
    assert conn.execute(text("SELECT id FROM medlm.uploads")).scalars().all() == [parent]
    assert (
        conn.execute(
            text("UPDATE medlm.uploads SET status='rejected' WHERE id=:id"), {"id": other}
        ).rowcount
        == 0
    )
    with rejected(conn):
        object_row(conn, first, other)
    with rejected(conn):
        object_row(conn, second, other)
    assert conn.scalar(text("SELECT count(*) FROM medlm.upload_safeguard_runs")) == 0


def test_retention_immutability_and_cancellation(schema):
    conn = schema
    owner, parent = upload(conn)
    obj = object_row(conn, owner, parent)
    for sql in (
        "UPDATE medlm.uploads SET expires_at=expires_at+interval '1 minute'",
        "UPDATE medlm.uploads SET ticket_expires_at=ticket_expires_at+interval '1 minute'",
        "UPDATE medlm.uploads SET declared_bytes=10485761",
        "UPDATE medlm.uploads SET purpose='clinical'",
        "DELETE FROM medlm.upload_objects",
        "DELETE FROM medlm.users",
    ):
        with rejected(conn):
            conn.execute(text(sql))
    conn.execute(
        text("""UPDATE medlm.upload_objects SET checksum_sha256=:hash,byte_size=100
        WHERE id=:id"""),
        {"id": obj, "hash": "0" * 64},
    )
    with rejected(conn):
        conn.execute(text("UPDATE medlm.upload_objects SET byte_size=101"))
    conn.execute(text("UPDATE medlm.uploads SET status='deleting',deletion_requested_at=now()"))
    with rejected(conn):
        object_row(conn, owner, parent)
    with rejected(conn):
        conn.execute(
            text("UPDATE medlm.uploads SET status='accepted',accepted_at=now(),consumed_at=now()")
        )
    with rejected(conn):
        conn.execute(text("UPDATE medlm.uploads SET status='deleted',purged_at=now()"))
    conn.execute(text("UPDATE medlm.upload_objects SET purged_at=now()"))
    conn.execute(text("UPDATE medlm.uploads SET status='deleted',purged_at=now()"))
    conn.execute(text("DELETE FROM medlm.users"))
    assert conn.scalar(text("SELECT count(*) FROM medlm.upload_objects")) == 0


def test_jobs_audit_and_receipt_retention(schema):
    conn = schema
    owner, parent = upload(conn)
    obj = object_row(conn, owner, parent)
    job = uuid4()
    values = {"id": job, "owner": owner, "parent": parent, "obj": obj}
    sql = text("""INSERT INTO medlm.upload_deletion_jobs(id,user_id,upload_id,object_id,reason)
        VALUES (:id,:owner,:parent,:obj,'expiry')""")
    conn.execute(sql, values)
    with rejected(conn):
        conn.execute(sql, {**values, "id": uuid4()})
    with rejected(conn):
        conn.execute(
            text("""UPDATE medlm.upload_deletion_jobs SET state='leased',
            lease_token=:token,lease_until=now()+interval '1 minute'"""),
            {"token": uuid4()},
        )
    conn.execute(
        text("""UPDATE medlm.upload_deletion_jobs SET state='leased',attempts=1,
        fencing_token=1,lease_token=:token,lease_until=now()+interval '1 minute'"""),
        {"token": uuid4()},
    )
    with rejected(conn):
        conn.execute(
            text("UPDATE medlm.upload_deletion_jobs SET lease_token=:token"), {"token": uuid4()}
        )
    with rejected(conn):
        conn.execute(
            text("""UPDATE medlm.upload_deletion_jobs SET state='completed',
            completed_at=now(),lease_until=NULL,lease_token=NULL""")
        )
    conn.execute(
        text("""INSERT INTO medlm.upload_audit_events
        VALUES (:id,:owner,:parent,'initiated',now(),now()+interval '30 days')"""),
        {"id": uuid4(), "owner": owner, "parent": parent},
    )
    with rejected(conn):
        conn.execute(text("UPDATE medlm.upload_audit_events SET event='accepted'"))
    conn.execute(
        text("""INSERT INTO medlm.upload_deletion_receipts
        VALUES (:id,:owner,:key,now(),now()+interval '30 days')"""),
        {"id": uuid4(), "owner": owner, "key": uuid4()},
    )
    with rejected(conn):
        conn.execute(
            text("UPDATE medlm.upload_deletion_receipts SET expires_at=expires_at+interval '1 day'")
        )
    with rejected(conn):
        conn.execute(text("DELETE FROM medlm.upload_deletion_receipts"))
    conn.execute(text("UPDATE medlm.upload_objects SET purged_at=now()"))
    conn.execute(text("DELETE FROM medlm.users"))
    assert conn.scalar(text("SELECT count(*) FROM medlm.upload_deletion_receipts")) == 1
    assert conn.scalar(text("SELECT user_id FROM medlm.upload_deletion_receipts")) is None


def test_downgrade_fails_closed_with_outstanding_inventory(isolated_database):
    engine, cfg = isolated_database
    command.upgrade(cfg, HEAD)
    with engine.begin() as conn:
        user, parent = upload(conn)
        object_row(conn, user, parent)
    with pytest.raises(DBAPIError):
        command.downgrade(cfg, "0001_foundation")
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
        assert conn.scalar(
            text(
                "SELECT relforcerowsecurity FROM pg_class WHERE oid='medlm.upload_objects'::regclass"
            )
        )


def test_insert_limits_and_owner_consistent_job(schema):
    conn = schema
    first, parent = upload(conn)
    second, other = upload(conn)
    obj = object_row(conn, first, parent)
    for field, value in (
        ("declared_bytes", "10485761"),
        ("expires_at", "now()+interval '25 hours'"),
        ("ticket_expires_at", "now()+interval '6 minutes'"),
        ("purpose", "'clinical'"),
    ):
        # Copy only metadata into a new row to exercise INSERT constraints, not update guards.
        columns = [
            "notice_version",
            "document_kind",
            "mime",
            "declared_bytes",
            "ticket_expires_at",
            "expires_at",
            "purpose",
        ]
        expressions = [value if column == field else column for column in columns]
        with rejected(conn):
            conn.execute(
                text(f"""INSERT INTO medlm.uploads
                (id,user_id,ticket_hash,{",".join(columns)})
                SELECT :id,user_id,:ticket,{",".join(expressions)}
                FROM medlm.uploads WHERE id=:parent"""),
                {"id": uuid4(), "ticket": uuid4().hex * 2, "parent": parent},
            )
    with rejected(conn):
        conn.execute(
            text("""INSERT INTO medlm.upload_deletion_jobs
            (id,user_id,upload_id,object_id,reason) VALUES (:id,:user,:parent,:object,'expiry')"""),
            {"id": uuid4(), "user": second, "parent": other, "object": obj},
        )
    with rejected(conn):
        conn.execute(
            text("""INSERT INTO medlm.upload_objects
            (id,user_id,upload_id,object_key,kind,expires_at)
            VALUES (:id,:user,:parent,:key,'review',now()+interval '2 hours')"""),
            {"id": uuid4(), "user": first, "parent": parent, "key": uuid4()},
        )


def test_cancellation_serializes_with_object_registration(isolated_database):
    engine, cfg = isolated_database
    command.upgrade(cfg, HEAD)
    with engine.begin() as conn:
        user, parent = upload(conn)
    with engine.connect() as cancel:
        tx = cancel.begin()
        cancel.execute(
            text("UPDATE medlm.uploads SET status='deleting',deletion_requested_at=now()")
        )
        try:
            with engine.connect() as writer:
                with pytest.raises(DBAPIError) as error:
                    with writer.begin():
                        writer.execute(text("SET LOCAL lock_timeout='100ms'"))
                        object_row(writer, user, parent)
                assert error.value.orig.sqlstate == "55P03"
            tx.commit()
        finally:
            if tx.is_active:
                tx.rollback()
    with engine.begin() as conn:
        with rejected(conn):
            object_row(conn, user, parent)
        assert conn.scalar(text("SELECT count(*) FROM medlm.upload_objects")) == 0


def test_downgrade_preserves_unexpired_receipts(isolated_database):
    engine, cfg = isolated_database
    command.upgrade(cfg, HEAD)
    with engine.begin() as conn:
        conn.execute(
            text("""INSERT INTO medlm.upload_deletion_receipts
            (id,object_key,verified_at,expires_at) VALUES
            (:id,:key,now(),now()+interval '30 days')"""),
            {"id": uuid4(), "key": uuid4()},
        )
    with pytest.raises(DBAPIError):
        command.downgrade(cfg, "0001_foundation")
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM medlm.upload_deletion_receipts")) == 1
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == HEAD

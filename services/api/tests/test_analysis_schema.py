"""Synthetic persistence tests against disposable PostgreSQL and real runtime RLS."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest
from alembic import command
from medlm_api.analysis_repository import AnalysisConflict, AnalysisRepository
from medlm_domain.analysis import ExtractionResult, MedicineFields, SyntheticProvenance
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_analysis_contracts import field
from test_upload_schema import isolated_database as _fixture
from test_upload_schema import snapshot

isolated_database = _fixture
ROOT = Path(__file__).resolve().parents[3]
HEAD = "0006_analysis_foundation"
TABLES = (
    "analysis_uploads",
    "analysis_jobs",
    "extraction_revisions",
    "identity_candidate_sets",
    "identity_candidates",
    "analysis_reviews",
    "analysis_prescription_drafts",
    "analysis_prescription_revisions",
    "analysis_prescription_lines",
    "analysis_prescription_confirmations",
    "analysis_prescription_confirmation_lines",
)
pytestmark = pytest.mark.database


def sql(conn, statement, **params):
    return conn.execute(text(statement), params)


@contextmanager
def rejected(conn):
    with pytest.raises(DBAPIError), conn.begin_nested():
        yield


@contextmanager
def runtime(engine, user):
    with engine.begin() as conn:
        sql(conn, "SET LOCAL ROLE medlm_runtime")
        sql(conn, "SELECT set_config('app.user_id',:u,true)", u=str(user) if user else "")
        yield conn


@pytest.fixture
def db(isolated_database):
    engine, cfg = isolated_database
    command.upgrade(cfg, HEAD)
    u, v = uuid4(), uuid4()
    with engine.begin() as conn:
        for name in (
            "runtime_grants.sql",
            "synthetic_upload_grants.sql",
            "synthetic_analysis_grants.sql",
        ):
            sql(conn, (ROOT / "database" / name).read_text())
        sql(conn, "INSERT INTO medlm.users(id) VALUES (:u),(:v)", u=u, v=v)
    return engine, cfg, u, v


def extraction(kind="medicine"):
    return ExtractionResult(
        document_kind="prescription" if kind == "prescription" else "strip",
        medicine=None
        if kind == "prescription"
        else MedicineFields(**{name: field() for name in MedicineFields.model_fields}),
        lines=(),
    )


def advance(conn, job):
    for state in ("validating", "extracting", "retrieving", "validating_output"):
        sql(conn, "UPDATE medlm.analysis_jobs SET state=:state WHERE id=:j", state=state, j=job)


def workflow(conn, user, kind="medicine"):
    repo = AnalysisRepository(conn, user)
    a = repo.create(kind=kind, locale="en-IN")
    j = repo.start_attempt(a, 1, uuid4())
    advance(conn, j)
    r = repo.publish(
        a,
        j,
        2,
        extraction(kind),
        SyntheticProvenance(fixture_id="synthetic-test", source_sha256="a" * 64),
    )
    return a, j, r


def candidates(conn, user, analysis, revision):
    s, c = uuid4(), uuid4()
    sql(
        conn,
        """INSERT INTO medlm.identity_candidate_sets
      (id,user_id,analysis_id,extraction_revision_id) VALUES (:s,:u,:a,:r)""",
        s=s,
        u=user,
        a=analysis,
        r=revision,
    )
    sql(
        conn,
        """INSERT INTO medlm.identity_candidates
      (id,user_id,analysis_id,extraction_revision_id,candidate_set_id,ordinal,observed_name)
      VALUES (:c,:u,:a,:r,:s,0,'Synthetic unverified text')""",
        c=c,
        u=user,
        a=analysis,
        r=revision,
        s=s,
    )
    return s, c


def review(conn, user, analysis, revision, candidate_set, candidate, version=3, key=None):
    return sql(
        conn,
        """INSERT INTO medlm.analysis_reviews
      (id,user_id,analysis_id,extraction_revision_id,candidate_set_id,candidate_id,
       request_key,analysis_version,decision,fields)
      VALUES (:id,:u,:a,:r,:s,:c,:key,:v,'confirm',
        '{"medicine":{"status":"confirmed","reviewed_value": null}}')""",
        id=uuid4(),
        u=user,
        a=analysis,
        r=revision,
        s=candidate_set,
        c=candidate,
        key=key or uuid4(),
        v=version,
    )


@pytest.mark.parametrize("baseline", ["base", "0005_manual_medications"])
def test_migration_roundtrip_preserves_legacy(isolated_database, baseline):
    engine, cfg = isolated_database
    if baseline != "base":
        command.upgrade(cfg, baseline)
    command.upgrade(cfg, "0005_manual_medications")
    u, a, p = uuid4(), uuid4(), uuid4()
    with engine.begin() as conn:
        before = snapshot(conn)
        sql(conn, "INSERT INTO medlm.users(id) VALUES (:u)", u=u)
        sql(
            conn,
            """INSERT INTO medlm.medicine_analyses(id,user_id,kind,country,locale)
          VALUES (:a,:u,'prescription','IN','en-IN')""",
            a=a,
            u=u,
        )
        sql(
            conn,
            "INSERT INTO medlm.prescriptions(id,user_id,analysis_id) VALUES (:p,:u,:a)",
            p=p,
            u=u,
            a=a,
        )
    command.upgrade(cfg, HEAD)
    with engine.connect() as conn:
        assert sql(conn, "SELECT version_num FROM alembic_version").scalar() == HEAD
        assert (
            sql(conn, "SELECT analysis_mode FROM medlm.medicine_analyses WHERE id=:a", a=a).scalar()
            is None
        )
        assert (
            sql(conn, "SELECT analysis_id FROM medlm.prescriptions WHERE id=:p", p=p).scalar() == a
        )
    command.downgrade(cfg, "0005_manual_medications")
    with engine.connect() as conn:
        assert snapshot(conn) == before
    command.upgrade(cfg, HEAD)


def test_populated_rollback_refuses_and_keeps_rls(db):
    engine, cfg, u, _ = db
    with runtime(engine, u) as conn:
        AnalysisRepository(conn, u).create(kind="medicine", locale="hi-IN")
    with pytest.raises(DBAPIError, match="export/erasure"):
        command.downgrade(cfg, "0005_manual_medications")
    with engine.connect() as conn:
        assert sql(conn, "SELECT version_num FROM alembic_version").scalar() == HEAD
        assert sql(
            conn,
            "SELECT bool_and(relforcerowsecurity) FROM pg_class WHERE relname=ANY(:names)",
            names=["medicine_analyses", *TABLES],
        ).scalar()


def test_fresh_base_to_head(isolated_database):
    engine, cfg = isolated_database
    command.upgrade(cfg, HEAD)  # Preserve the Chunk 2 migration checkpoint.
    with engine.connect() as conn:
        assert sql(conn, "SELECT version_num FROM alembic_version").scalar() == HEAD
        for table in TABLES:
            assert sql(conn, f"SELECT count(*) FROM medlm.{table}").scalar() == 0


def test_stable_parent_reextraction_stale_publication_and_immutable_history(db):
    engine, _, u, _ = db
    with runtime(engine, u) as conn:
        a, j, r = workflow(conn, u)
        repo = AnalysisRepository(conn, u)
        with rejected(conn):
            sql(conn, "UPDATE medlm.analysis_jobs SET state='queued' WHERE id=:j", j=j)
        with rejected(conn):
            sql(conn, "UPDATE medlm.extraction_revisions SET observations='{}' WHERE id=:r", r=r)
        j2 = repo.start_attempt(a, 3, uuid4())
        with pytest.raises(AnalysisConflict):
            repo.publish(
                a,
                j,
                4,
                extraction(),
                SyntheticProvenance(fixture_id="test", source_sha256="a" * 64),
            )
        with pytest.raises(AnalysisConflict):
            repo.start_attempt(a, 3, uuid4())
        advance(conn, j2)
        r2 = repo.publish(
            a, j2, 4, extraction(), SyntheticProvenance(fixture_id="test", source_sha256="a" * 64)
        )
        assert sql(conn, "SELECT count(*) FROM medlm.medicine_analyses").scalar() == 1
        assert sql(
            conn, "SELECT revision FROM medlm.extraction_revisions ORDER BY revision"
        ).scalars().all() == [1, 2]
        assert (
            sql(
                conn, "SELECT current_revision_id FROM medlm.medicine_analyses WHERE id=:a", a=a
            ).scalar()
            == r2
        )
        with rejected(conn):
            sql(
                conn,
                "UPDATE medlm.medicine_analyses SET current_revision_id=:r,version=version+1 WHERE id=:a",
                r=r,
                a=a,
            )
        with rejected(conn):
            sql(
                conn,
                "INSERT INTO medlm.analysis_jobs(id,user_id,analysis_id,attempt,request_key) SELECT :id,user_id,analysis_id,3,request_key FROM medlm.analysis_jobs WHERE id=:j",
                id=uuid4(),
                j=j2,
            )
        repo.cancel(a, 5)
        with pytest.raises(AnalysisConflict):
            repo.start_attempt(a, 6, uuid4())
        repo.erase(a, 6)
        assert sql(conn, "SELECT count(*) FROM medlm.extraction_revisions").scalar() == 0


def test_real_concurrent_attempts_only_one_can_advance(db):
    engine, _, u, _ = db
    with runtime(engine, u) as conn:
        a = AnalysisRepository(conn, u).create(kind="medicine", locale="te-IN")
    started = Event()

    def second():
        with runtime(engine, u) as conn:
            sql(conn, "SET LOCAL lock_timeout='5s'")
            started.set()
            with pytest.raises(AnalysisConflict):
                AnalysisRepository(conn, u).start_attempt(a, 1, uuid4())

    with ThreadPoolExecutor(max_workers=1) as pool:
        with runtime(engine, u) as conn:
            AnalysisRepository(conn, u).start_attempt(a, 1, uuid4())
            future = pool.submit(second)
            assert started.wait(3)
        future.result(timeout=10)
    with runtime(engine, u) as conn:
        assert sql(conn, "SELECT count(*) FROM medlm.analysis_jobs").scalar() == 1


def test_review_exact_binding_replay_staleness_and_sealed_sets(db):
    engine, _, u, _ = db
    with runtime(engine, u) as conn:
        a, _, r = workflow(conn, u)
        s, c = candidates(conn, u, a, r)
        other, _, other_r = workflow(conn, u)
        other_s, other_c = candidates(conn, u, other, other_r)
        with rejected(conn):
            review(conn, u, a, r, other_s, other_c)
        with rejected(conn):
            review(conn, u, a, r, s, other_c)
        key = uuid4()
        review(conn, u, a, r, s, c, key=key)
        with rejected(conn):
            review(conn, u, a, r, s, c, key=key)
        assert (
            sql(
                conn, "SELECT verification FROM medlm.extraction_revisions WHERE id=:r", r=r
            ).scalar()
            == "unverified"
        )
        AnalysisRepository(conn, u).start_attempt(a, 3, uuid4())
        with rejected(conn):
            review(conn, u, a, r, s, c, version=4)
        with rejected(conn):
            sql(conn, "UPDATE medlm.analysis_reviews SET decision='reject'")
    with runtime(engine, u) as conn:
        with rejected(conn):
            sql(
                conn,
                """INSERT INTO medlm.identity_candidates
              (id,user_id,analysis_id,extraction_revision_id,candidate_set_id,ordinal,observed_name)
              VALUES (:id,:u,:a,:r,:s,1,'Synthetic')""",
                id=uuid4(),
                u=u,
                a=other,
                r=other_r,
                s=other_s,
            )


def test_owner_isolation_and_cross_owner_fks(db):
    engine, _, u, v = db
    with runtime(engine, u) as conn:
        a, j, r = workflow(conn, u, "prescription")
        s, c = candidates(conn, u, a, r)
        review(conn, u, a, r, s, c)
        _, d, pr, _ = prescription(conn, u, a, r)
        confirm(conn, u, a, d, pr)
        up = upload(conn, u, True)
        sql(
            conn,
            """INSERT INTO medlm.analysis_uploads(id,user_id,analysis_id,upload_id)
          VALUES (:id,:u,:a,:up)""",
            id=uuid4(),
            u=u,
            a=a,
            up=up,
        )
        for table in TABLES:
            assert sql(conn, f"SELECT count(*) FROM medlm.{table}").scalar() == 1
    for user in (v, None):
        with runtime(engine, user) as conn:
            for table in ("medicine_analyses", *TABLES):
                assert sql(conn, f"SELECT count(*) FROM medlm.{table}").scalar() == 0
            with pytest.raises(AnalysisConflict):
                AnalysisRepository(conn, v).start_attempt(a, 3, uuid4())
            with rejected(conn):
                review(conn, v, a, r, s, c)
    # Even the test owner, which can see both tenants, cannot forge the composite FK.
    with engine.begin() as conn:
        with rejected(conn):
            sql(
                conn,
                "INSERT INTO medlm.prescriptions(id,user_id,analysis_id) VALUES (:id,:v,:a)",
                id=uuid4(),
                v=v,
                a=a,
            )
        with rejected(conn):
            sql(
                conn,
                """INSERT INTO medlm.analysis_jobs(id,user_id,analysis_id,attempt,request_key)
              VALUES (:id,:v,:a,2,:key)""",
                id=uuid4(),
                v=v,
                a=a,
                key=uuid4(),
            )


def prescription(conn, u, a, r):
    p, d, pr, line = (uuid4() for _ in range(4))
    sql(
        conn,
        "INSERT INTO medlm.prescriptions(id,user_id,analysis_id) VALUES (:p,:u,:a)",
        p=p,
        u=u,
        a=a,
    )
    sql(
        conn,
        """INSERT INTO medlm.analysis_prescription_drafts(id,user_id,analysis_id,prescription_id)
      VALUES (:d,:u,:a,:p)""",
        d=d,
        u=u,
        a=a,
        p=p,
    )
    sql(
        conn,
        """INSERT INTO medlm.analysis_prescription_revisions
      (id,user_id,analysis_id,draft_id,extraction_revision_id,revision) VALUES (:r,:u,:a,:d,:e,1)""",
        r=pr,
        u=u,
        a=a,
        d=d,
        e=r,
    )
    sql(
        conn,
        """INSERT INTO medlm.analysis_prescription_lines
      (id,user_id,analysis_id,draft_id,prescription_revision_id,ordinal,fields)
      VALUES (:id,:u,:a,:d,:r,0,'{"medicine": null,"strength": null,"dose": null}')""",
        id=line,
        u=u,
        a=a,
        d=d,
        r=pr,
    )
    return p, d, pr, line


def confirm(conn, u, a, d, r, version=3, with_lines=True):
    identity = uuid4()
    sql(
        conn,
        """INSERT INTO medlm.analysis_prescription_confirmations
      (id,user_id,analysis_id,draft_id,prescription_revision_id,request_key,analysis_version,reviewed_fields)
      VALUES (:id,:u,:a,:d,:r,:key,:v,'{"line_disposition":"unresolved"}')""",
        id=identity,
        u=u,
        a=a,
        d=d,
        r=r,
        key=uuid4(),
        v=version,
    )
    if with_lines:
        for line in sql(
            conn,
            "SELECT id FROM medlm.analysis_prescription_lines WHERE user_id=:u AND prescription_revision_id=:r",
            u=u,
            r=r,
        ).scalars():
            confirmation_line(conn, u, a, d, r, identity, line)
    return identity


def confirmation_line(conn, u, a, d, r, confirmation, line):
    sql(
        conn,
        """INSERT INTO medlm.analysis_prescription_confirmation_lines
      (id,user_id,analysis_id,draft_id,prescription_revision_id,confirmation_id,line_id,
       disposition,reviewed_fields)
      VALUES (:id,:u,:a,:d,:r,:c,:line,'unresolved','{}')""",
        id=uuid4(),
        u=u,
        a=a,
        d=d,
        r=r,
        c=confirmation,
        line=line,
    )


def test_prescription_revision_confirmation_ownership_and_erasure(db):
    engine, _, u, v = db
    with runtime(engine, u) as conn:
        a, _, r = workflow(conn, u, "prescription")
        p, d, pr, line = prescription(conn, u, a, r)
        confirm(conn, u, a, d, pr)
        with rejected(conn):
            confirm(conn, u, a, d, pr)
        for table in (
            "analysis_prescription_revisions",
            "analysis_prescription_lines",
            "analysis_prescription_confirmations",
        ):
            with rejected(conn):
                sql(conn, f"UPDATE medlm.{table} SET user_id=:u", u=u)
    with runtime(engine, v) as conn:
        with rejected(conn):
            confirm(conn, v, a, d, pr)
    with runtime(engine, u) as conn:
        with rejected(conn):
            sql(
                conn,
                """INSERT INTO medlm.analysis_prescription_lines
              (id,user_id,analysis_id,draft_id,prescription_revision_id,ordinal,fields)
              VALUES (:id,:u,:a,:d,:r,1,'{}')""",
                id=uuid4(),
                u=u,
                a=a,
                d=d,
                r=pr,
            )
        AnalysisRepository(conn, u).start_attempt(a, 3, uuid4())
        with rejected(conn):
            confirm(conn, u, a, d, pr, version=4)
        AnalysisRepository(conn, u).erase(a, 4)
        for table in ("prescriptions", *TABLES):
            assert sql(conn, f"SELECT count(*) FROM medlm.{table}").scalar() == 0


def upload(conn, u, retain):
    up = uuid4()
    sql(
        conn,
        """INSERT INTO medlm.uploads(id,user_id,notice_version,document_kind,mime,
      declared_bytes,ticket_hash,ticket_expires_at,expires_at,retain_for_review)
      VALUES (:id,:u,'test','strip','image/png',10,:hash,now()+interval '5 minutes',
        now()+interval '1 hour',:retain)""",
        id=up,
        u=u,
        hash=uuid4().hex * 2,
        retain=retain,
    )
    sql(
        conn,
        "UPDATE medlm.uploads SET consumed_at=now(),accepted_at=now(),status='accepted' WHERE id=:id",
        id=up,
    )
    return up


def test_upload_retention_gate_and_inventory_not_erased(db):
    engine, _, u, v = db
    with runtime(engine, u) as conn:
        repo = AnalysisRepository(conn, u)
        a = repo.create(kind="medicine", locale="en-IN")
        no = upload(conn, u, False)
        with rejected(conn):
            sql(
                conn,
                "INSERT INTO medlm.analysis_uploads(id,user_id,analysis_id,upload_id) VALUES (:id,:u,:a,:up)",
                id=uuid4(),
                u=u,
                a=a,
                up=no,
            )
        up = upload(conn, u, True)
        sql(
            conn,
            "INSERT INTO medlm.analysis_uploads(id,user_id,analysis_id,upload_id) VALUES (:id,:u,:a,:up)",
            id=uuid4(),
            u=u,
            a=a,
            up=up,
        )
        repo.erase(a, 1)
        assert sql(conn, "SELECT count(*) FROM medlm.uploads").scalar() == 2
        assert sql(conn, "SELECT count(*) FROM medlm.analysis_uploads").scalar() == 0


def test_grants_force_rls_no_bypass_or_security_definer(db):
    engine, _, _, _ = db
    with engine.connect() as conn:
        role = sql(
            conn,
            "SELECT rolsuper,rolcreatedb,rolcreaterole,rolbypassrls FROM pg_roles WHERE rolname='medlm_runtime'",
        ).one()
        assert not any(role)
        for table in TABLES:
            assert sql(
                conn,
                "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid=CAST(:t AS regclass)",
                t=f"medlm.{table}",
            ).scalar()
            assert (
                sql(
                    conn,
                    "SELECT count(*) FROM pg_policies WHERE schemaname='medlm' AND tablename=:t AND policyname='owner_access'",
                    t=table,
                ).scalar()
                == 1
            )
            assert not sql(
                conn, "SELECT has_table_privilege('medlm_runtime',:t,'DELETE')", t=f"medlm.{table}"
            ).scalar()
            if table != "analysis_jobs":
                assert not sql(
                    conn,
                    "SELECT has_table_privilege('medlm_runtime',:t,'UPDATE')",
                    t=f"medlm.{table}",
                ).scalar()
            assert not sql(
                conn,
                "SELECT has_table_privilege('medlm_upload_worker',:t,'SELECT')",
                t=f"medlm.{table}",
            ).scalar()
        for table in (
            "verification_sources",
            "prescription_medicines",
            "prescription_confirmations",
        ):
            assert not sql(
                conn, "SELECT has_table_privilege('medlm_runtime',:t,'SELECT')", t=f"medlm.{table}"
            ).scalar()
        assert (
            sql(
                conn,
                """SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
          WHERE n.nspname='medlm' AND p.prosecdef""",
            ).scalar()
            == 0
        )


def test_owner_cannot_rewrite_history_even_with_table_privileges(db):
    engine, _, u, _ = db
    with runtime(engine, u) as conn:
        a, j, r = workflow(conn, u, "prescription")
        s, c = candidates(conn, u, a, r)
        review(conn, u, a, r, s, c)
        _, d, pr, _ = prescription(conn, u, a, r)
        confirm(conn, u, a, d, pr)
    with engine.begin() as conn:
        for table in TABLES:
            if table in ("analysis_uploads", "analysis_jobs"):
                continue
            with rejected(conn):
                sql(conn, f"UPDATE medlm.{table} SET user_id=user_id")
        with rejected(conn):
            sql(conn, "UPDATE medlm.analysis_jobs SET state='failed' WHERE id=:j", j=j)


def test_current_pointer_version_and_direct_stale_job_guard(db):
    engine, _, u, _ = db
    with runtime(engine, u) as conn:
        repo = AnalysisRepository(conn, u)
        a = repo.create(kind="medicine", locale="en-IN")
        j = repo.start_attempt(a, 1, uuid4())
        advance(conn, j)
        newer = repo.start_attempt(a, 2, uuid4())
        with rejected(conn):
            sql(
                conn,
                """INSERT INTO medlm.extraction_revisions
              (id,user_id,analysis_id,job_id,revision,observations,fixture_id,fixture_sha256)
              VALUES (:id,:u,:a,:j,1,'{}','synthetic',:hash)""",
                id=uuid4(),
                u=u,
                a=a,
                j=j,
                hash="a" * 64,
            )
        with rejected(conn):
            sql(conn, "UPDATE medlm.medicine_analyses SET current_job_id=:j WHERE id=:a", j=j, a=a)
        with rejected(conn):
            sql(conn, "UPDATE medlm.analysis_jobs SET state='completed' WHERE id=:j", j=newer)
        assert sql(conn, "SELECT count(*) FROM medlm.extraction_revisions").scalar() == 0


def test_concurrent_publications_have_one_winner(db):
    engine, _, u, _ = db
    with runtime(engine, u) as conn:
        repo = AnalysisRepository(conn, u)
        a = repo.create(kind="medicine", locale="en-IN")
        j = repo.start_attempt(a, 1, uuid4())
        advance(conn, j)
    started = Event()
    provenance = SyntheticProvenance(fixture_id="test", source_sha256="a" * 64)

    def second():
        with runtime(engine, u) as conn:
            sql(conn, "SET LOCAL lock_timeout='5s'")
            started.set()
            with pytest.raises(AnalysisConflict):
                AnalysisRepository(conn, u).publish(a, j, 2, extraction(), provenance)

    with ThreadPoolExecutor(max_workers=1) as pool:
        with runtime(engine, u) as conn:
            published = AnalysisRepository(conn, u).publish(a, j, 2, extraction(), provenance)
            future = pool.submit(second)
            assert started.wait(3)
        future.result(timeout=10)
    with runtime(engine, u) as conn:
        assert sql(conn, "SELECT id FROM medlm.extraction_revisions").scalars().all() == [published]


def test_upload_inventory_guard_and_metadata_expiry_keep_text(db):
    engine, _, u, _ = db
    with runtime(engine, u) as conn:
        a, _, r = workflow(conn, u)
        up = upload(conn, u, True)
        sql(
            conn,
            """INSERT INTO medlm.analysis_uploads(id,user_id,analysis_id,upload_id)
          VALUES (:id,:u,:a,:up)""",
            id=uuid4(),
            u=u,
            a=a,
            up=up,
        )
        obj = uuid4()
        sql(
            conn,
            """INSERT INTO medlm.upload_objects(id,user_id,upload_id,object_key,kind,expires_at)
          SELECT :id,:u,:up,:key,'review',expires_at FROM medlm.uploads WHERE id=:up""",
            id=obj,
            u=u,
            up=up,
            key=uuid4(),
        )
    with engine.begin() as conn:
        with rejected(conn):
            sql(conn, "DELETE FROM medlm.uploads WHERE id=:up", up=up)
        # Simulate verified purge metadata only; no storage execution is implemented here.
        sql(conn, "UPDATE medlm.upload_objects SET purged_at=now() WHERE id=:id", id=obj)
        sql(conn, "SET LOCAL ROLE medlm_upload_worker")
        sql(conn, "DELETE FROM medlm.uploads WHERE id=:up", up=up)
        sql(conn, "RESET ROLE")
        assert sql(conn, "SELECT count(*) FROM medlm.analysis_uploads").scalar() == 0
        assert sql(conn, "SELECT id FROM medlm.extraction_revisions").scalar() == r


def test_cross_owner_candidates_and_prescription_links_rejected_by_fk(db):
    engine, _, u, v = db
    with runtime(engine, u) as conn:
        a, _, r = workflow(conn, u, "prescription")
        _, d, pr, _ = prescription(conn, u, a, r)
    with runtime(engine, v) as conn:
        b, _, br = workflow(conn, v, "prescription")
        s, c = candidates(conn, v, b, br)
    with engine.begin() as conn:
        with rejected(conn):
            sql(
                conn,
                """INSERT INTO medlm.analysis_prescription_lines
              (id,user_id,analysis_id,draft_id,prescription_revision_id,ordinal,fields)
              VALUES (:id,:v,:b,:d,:r,1,'{}')""",
                id=uuid4(),
                v=v,
                b=b,
                d=d,
                r=pr,
            )
        with rejected(conn):
            review(conn, u, a, r, s, c)


def test_partial_publication_cannot_commit(db):
    engine, _, u, _ = db
    with runtime(engine, u) as conn:
        repo = AnalysisRepository(conn, u)
        a = repo.create(kind="medicine", locale="en-IN")
        j = repo.start_attempt(a, 1, uuid4())
        advance(conn, j)
    with pytest.raises(DBAPIError, match="Incomplete extraction publication"):
        with runtime(engine, u) as conn:
            sql(
                conn,
                """INSERT INTO medlm.extraction_revisions
              (id,user_id,analysis_id,job_id,revision,observations,fixture_id,fixture_sha256)
              VALUES (:id,:u,:a,:j,1,'{}','synthetic',:hash)""",
                id=uuid4(),
                u=u,
                a=a,
                j=j,
                hash="a" * 64,
            )
    with runtime(engine, u) as conn:
        assert sql(conn, "SELECT count(*) FROM medlm.extraction_revisions").scalar() == 0
        AnalysisRepository(conn, u).publish(
            a,
            j,
            2,
            extraction(),
            SyntheticProvenance(fixture_id="synthetic", source_sha256="a" * 64),
        )


def test_confirmation_lines_reject_foreign_revision_and_duplicate(db):
    engine, _, u, v = db
    with runtime(engine, u) as conn:
        a, _, r = workflow(conn, u, "prescription")
        _, d, pr, line = prescription(conn, u, a, r)
        other, _, other_r = workflow(conn, u, "prescription")
        _, _, _, other_line = prescription(conn, u, other, other_r)
        c = confirm(conn, u, a, d, pr, with_lines=False)
        with rejected(conn):
            confirmation_line(conn, u, a, d, pr, c, other_line)
        confirmation_line(conn, u, a, d, pr, c, line)
        with rejected(conn):
            confirmation_line(conn, u, a, d, pr, c, line)
    with runtime(engine, v) as conn:
        with rejected(conn):
            confirmation_line(conn, v, a, d, pr, c, line)
        assert (
            sql(
                conn, "SELECT count(*) FROM medlm.analysis_prescription_confirmation_lines"
            ).scalar()
            == 0
        )
    with runtime(engine, u) as conn:
        with rejected(conn):
            confirmation_line(conn, u, a, d, pr, c, line)
        with rejected(conn):
            sql(
                conn,
                "UPDATE medlm.analysis_prescription_confirmation_lines SET disposition='included'",
            )


@pytest.mark.parametrize("partial", [False, True])
def test_confirmation_requires_complete_line_coverage_at_commit(db, partial):
    engine, _, u, _ = db
    with runtime(engine, u) as conn:
        a, _, r = workflow(conn, u, "prescription")
        _, d, pr, line = prescription(conn, u, a, r)
        sql(
            conn,
            """INSERT INTO medlm.analysis_prescription_lines
          (id,user_id,analysis_id,draft_id,prescription_revision_id,ordinal,fields)
          VALUES (:id,:u,:a,:d,:r,1,'{}')""",
            id=uuid4(),
            u=u,
            a=a,
            d=d,
            r=pr,
        )
    with pytest.raises(DBAPIError, match="every line disposition"):
        with runtime(engine, u) as conn:
            c = confirm(conn, u, a, d, pr, with_lines=False)
            if partial:
                confirmation_line(conn, u, a, d, pr, c, line)
    with runtime(engine, u) as conn:
        assert (
            sql(conn, "SELECT count(*) FROM medlm.analysis_prescription_confirmations").scalar()
            == 0
        )
        confirm(conn, u, a, d, pr)
        assert (
            sql(
                conn, "SELECT count(*) FROM medlm.analysis_prescription_confirmation_lines"
            ).scalar()
            == 2
        )

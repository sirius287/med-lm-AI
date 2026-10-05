from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_upload_schema import isolated_database as _fixture
from test_upload_schema import snapshot

isolated_database = _fixture
ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("baseline", ["base", "0001_foundation", "0004_upload_runtime"])
def test_additive_migration_roundtrip(isolated_database, baseline):
    engine, cfg = isolated_database
    if baseline != "base":
        command.upgrade(cfg, baseline)
        with engine.begin() as conn:
            user, id = uuid4(), uuid4()
            conn.execute(text("INSERT INTO medlm.users(id) VALUES (:id)"), {"id": user})
            conn.execute(
                text("""INSERT INTO medlm.medications
                (id,user_id,display_name,dose_text,origin,instruction_snapshot,reviewed_at)
                VALUES (:id,:u,'Legacy synthetic','Literal','manual','{}',now())"""),
                {"id": id, "u": user},
            )
    command.upgrade(cfg, "0004_upload_runtime")
    with engine.connect() as conn:
        before = snapshot(conn)
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        assert (
            conn.scalar(text("SELECT version_num FROM alembic_version"))
            == "0005_manual_medications"
        )
        if baseline != "base":
            assert (
                conn.scalar(
                    text("SELECT display_name FROM medlm.medications WHERE id=:id"), {"id": id}
                )
                == "Legacy synthetic"
            )
            assert (
                conn.scalar(
                    text("SELECT current_instruction_id FROM medlm.medications WHERE id=:id"),
                    {"id": id},
                )
                is None
            )
        assert conn.scalar(text("SELECT count(*) FROM medlm.medication_instruction_revisions")) == 0
    command.downgrade(cfg, "0004_upload_runtime")
    with engine.connect() as conn:
        assert snapshot(conn) == before
    command.upgrade(cfg, "head")


def test_runtime_rls_and_append_only_guards(isolated_database):
    engine, cfg = isolated_database
    command.upgrade(cfg, "head")
    u, v, m, r = uuid4(), uuid4(), uuid4(), uuid4()
    with engine.begin() as conn:
        conn.execute(text((ROOT / "database/runtime_grants.sql").read_text()))
        conn.execute(text("INSERT INTO medlm.users(id) VALUES (:u),(:v)"), {"u": u, "v": v})
        conn.execute(
            text("""INSERT INTO medlm.medications(id,user_id,display_name,dose_text,origin,instruction_snapshot,reviewed_at)
            VALUES (:m,:u,'Synthetic','Literal','manual','{}',now())"""),
            {"m": m, "u": u},
        )
        conn.execute(
            text("""INSERT INTO medlm.medication_instruction_revisions(id,user_id,medication_id,revision,fields,origin)
            VALUES (:r,:u,:m,1,'{}','manual')"""),
            {"r": r, "u": u, "m": m},
        )
        conn.execute(text("SET LOCAL ROLE medlm_runtime"))
        assert conn.scalar(text("SELECT count(*) FROM medlm.medications")) == 0
        conn.execute(text("SELECT set_config('app.user_id',:u,true)"), {"u": str(v)})
        assert conn.scalar(text("SELECT count(*) FROM medlm.medications")) == 0
        with pytest.raises(DBAPIError), conn.begin_nested():
            conn.execute(
                text("""INSERT INTO medlm.medication_instruction_revisions(id,user_id,medication_id,revision,fields,origin)
                VALUES (:r,:u,:m,2,'{}','manual')"""),
                {"r": uuid4(), "u": v, "m": m},
            )
        conn.execute(text("SELECT set_config('app.user_id',:u,true)"), {"u": str(u)})
        assert conn.scalar(text("SELECT count(*) FROM medlm.medications")) == 1
        with pytest.raises(DBAPIError), conn.begin_nested():
            conn.execute(
                text("UPDATE medlm.medication_instruction_revisions SET fields='{}' WHERE id=:r"),
                {"r": r},
            )
        with pytest.raises(DBAPIError), conn.begin_nested():
            conn.execute(text("SELECT * FROM medlm.prescriptions"))
    with pytest.raises(DBAPIError):
        command.downgrade(cfg, "0004_upload_runtime")

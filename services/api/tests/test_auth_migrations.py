from uuid import uuid4

from alembic import command
from sqlalchemy import text
from test_upload_schema import isolated_database as _database_fixture

isolated_database = _database_fixture


def test_auth_migration_preserves_legacy_session(isolated_database):
    engine, cfg = isolated_database
    command.upgrade(cfg, "0002_synthetic_uploads")
    user = uuid4()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO medlm.users(id) VALUES (:id)"), {"id": user})
        conn.execute(
            text("""INSERT INTO medlm_auth.web_sessions
          VALUES ('synthetic-cookie-hash',:id,'opaque-test-ciphertext','synthetic-csrf',
          now()+interval '1 hour',NULL)"""),
            {"id": user},
        )
        original = conn.execute(text("SELECT * FROM medlm_auth.web_sessions")).first()
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        updated = conn.execute(text("SELECT * FROM medlm_auth.web_sessions")).first()
        assert tuple(updated[:-1]) == tuple(original)
        assert updated.provider_session_id is None
    command.downgrade(cfg, "0002_synthetic_uploads")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT * FROM medlm_auth.web_sessions")).first() == original
    command.upgrade(cfg, "head")

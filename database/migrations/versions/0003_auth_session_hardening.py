"""Add session identity binding and private shared auth throttles."""

from alembic import op

revision = "0003_auth_session_hardening"
down_revision = "0002_synthetic_uploads"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE medlm_auth.web_sessions ADD COLUMN provider_session_id uuid")
    op.execute(
        "CREATE INDEX web_session_provider ON medlm_auth.web_sessions(user_id,provider_session_id)"
    )
    op.execute("""CREATE TABLE medlm_auth.auth_throttles (
        key_hash text PRIMARY KEY CHECK(key_hash ~ '^[0-9a-f]{64}$'),
        window_end timestamptz NOT NULL,
        attempts int NOT NULL CHECK(attempts BETWEEN 1 AND 11)
    )""")
    op.execute("CREATE INDEX auth_throttle_expiry ON medlm_auth.auth_throttles(window_end)")
    op.execute("REVOKE ALL ON medlm_auth.auth_throttles FROM PUBLIC")


def downgrade():
    op.execute("DROP TABLE medlm_auth.auth_throttles")
    op.execute("DROP INDEX medlm_auth.web_session_provider")
    op.execute("ALTER TABLE medlm_auth.web_sessions DROP COLUMN provider_session_id")

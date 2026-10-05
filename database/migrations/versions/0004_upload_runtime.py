"""Synthetic upload idempotency and narrowly scoped maintenance policies."""

from alembic import op

revision = "0004_upload_runtime"
down_revision = "0003_auth_session_hardening"
branch_labels = None
depends_on = None

TABLES = (
    "uploads",
    "upload_objects",
    "upload_deletion_jobs",
    "upload_audit_events",
    "upload_deletion_receipts",
    "upload_safeguard_runs",
)


def upgrade():
    op.execute("""ALTER TABLE medlm.uploads
      ADD COLUMN request_key uuid,
      ADD COLUMN request_hash text CHECK(request_hash ~ '^[0-9a-f]{64}$'),
      ADD COLUMN source_checksum_sha256 text
        CHECK(source_checksum_sha256 ~ '^[0-9a-f]{64}$'),
      ADD CONSTRAINT upload_request_metadata CHECK
        ((request_key IS NULL AND request_hash IS NULL AND source_checksum_sha256 IS NULL)
         OR (request_key IS NOT NULL AND request_hash IS NOT NULL
             AND source_checksum_sha256 IS NOT NULL)),
      ADD CONSTRAINT upload_request_unique UNIQUE(user_id,request_key);
    """)
    # Role is provisioned separately, never granted to the API. No BYPASSRLS/definer.
    for table in TABLES:
        op.execute(f"""CREATE POLICY upload_maintenance ON medlm.{table}
          USING(current_user = 'medlm_upload_worker')
          WITH CHECK(current_user = 'medlm_upload_worker')""")
    op.execute("""CREATE POLICY upload_health_read ON medlm.upload_safeguard_runs
        FOR SELECT USING(current_user = 'medlm_runtime')""")


def downgrade():
    op.execute("DROP POLICY upload_health_read ON medlm.upload_safeguard_runs")
    for table in TABLES:
        op.execute(f"DROP POLICY upload_maintenance ON medlm.{table}")
    op.execute("""ALTER TABLE medlm.uploads DROP COLUMN request_key,
        DROP COLUMN request_hash, DROP COLUMN source_checksum_sha256""")

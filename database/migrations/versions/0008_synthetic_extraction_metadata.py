"""Synthetic adapter metadata only; existing hashes/contracts remain authoritative."""

from alembic import op
from sqlalchemy import text

revision = "0008_synthetic_extraction"
down_revision = "0007_analysis_lifecycle"
branch_labels = None
depends_on = None


def amend(reverse=False):
    old = "-'fencing_token'-'lifecycle_version'"
    new = old + "-'safe_error_code'"
    definition = op.get_bind().scalar(
        text("SELECT pg_get_functiondef('medlm.guard_analysis_child()'::regprocedure)")
    )
    source, target = (new, old) if reverse else (old, new)
    if source not in definition:
        raise RuntimeError("Unexpected analysis guard")
    op.execute(definition.replace(source, target))


def upgrade():
    op.execute("""
    ALTER TABLE medlm.extraction_revisions
      ADD COLUMN fixture_revision int,
      ADD COLUMN sanitized_sha256 text,
      ADD COLUMN provider_id text,
      ADD COLUMN model_id text,
      ADD COLUMN pipeline_version text,
      ADD CONSTRAINT extraction_metadata_complete CHECK (
        (fixture_revision IS NULL AND sanitized_sha256 IS NULL AND provider_id IS NULL
          AND model_id IS NULL AND pipeline_version IS NULL)
        OR (fixture_revision IS NOT NULL AND fixture_revision>0
          AND sanitized_sha256 IS NOT NULL AND sanitized_sha256 ~ '^[a-f0-9]{64}$'
          AND provider_id IS NOT NULL AND provider_id ~ '^[a-z0-9_-]{1,80}$'
          AND model_id IS NOT NULL AND model_id ~ '^[a-z0-9_-]{1,80}$'
          AND pipeline_version IS NOT NULL AND pipeline_version ~ '^[a-z0-9_-]{1,80}$'));
    ALTER TABLE medlm.analysis_jobs ADD COLUMN safe_error_code text,
      ADD CONSTRAINT extraction_safe_error CHECK (safe_error_code IS NULL OR
        (state='failed' AND safe_error_code IN ('adapter_failure','invalid_output')) OR
        (state='needs_input' AND safe_error_code='no_observations'));
    CREATE FUNCTION medlm.guard_extraction_metadata() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.fixture_revision IS NOT NULL THEN
        IF NEW.provenance<>'synthetic' OR NEW.verification<>'unverified'
          OR NEW.contract_version<>1 OR NEW.fixture_revision<>1
          OR NEW.provider_id<>'synthetic' OR NEW.model_id<>'deterministic-v1'
          OR NEW.pipeline_version<>'synthetic-extraction-v1'
          THEN RAISE EXCEPTION 'Unsupported synthetic extraction metadata'; END IF;
        PERFORM 1 FROM medlm.analysis_uploads l JOIN medlm.uploads u
          ON (u.user_id,u.id)=(l.user_id,l.upload_id)
          JOIN medlm.upload_objects o ON (o.user_id,o.upload_id)=(u.user_id,u.id)
          WHERE l.user_id=NEW.user_id AND l.analysis_id=NEW.analysis_id
            AND u.source_checksum_sha256=NEW.fixture_sha256
            AND o.checksum_sha256=NEW.sanitized_sha256 AND o.purged_at IS NULL
            AND o.expires_at>clock_timestamp() AND u.status='accepted' AND u.retain_for_review;
        IF NOT FOUND THEN RAISE EXCEPTION 'Extraction content binding mismatch'; END IF;
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER extraction_metadata_guard BEFORE INSERT ON medlm.extraction_revisions
      FOR EACH ROW EXECUTE FUNCTION medlm.guard_extraction_metadata();
    REVOKE ALL ON FUNCTION medlm.guard_extraction_metadata() FROM PUBLIC;
    """)
    amend()


def downgrade():
    op.execute("""
    ALTER TABLE medlm.extraction_revisions NO FORCE ROW LEVEL SECURITY;
    ALTER TABLE medlm.analysis_jobs NO FORCE ROW LEVEL SECURITY;
    DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM medlm.extraction_revisions WHERE fixture_revision IS NOT NULL)
        OR EXISTS(SELECT 1 FROM medlm.analysis_jobs WHERE safe_error_code IS NOT NULL)
        THEN RAISE EXCEPTION 'Extraction metadata exists; explicit export/erasure required'; END IF;
    END $$;
    ALTER TABLE medlm.extraction_revisions FORCE ROW LEVEL SECURITY;
    ALTER TABLE medlm.analysis_jobs FORCE ROW LEVEL SECURITY;
    DROP TRIGGER extraction_metadata_guard ON medlm.extraction_revisions;
    DROP FUNCTION medlm.guard_extraction_metadata();
    """)
    amend(reverse=True)
    op.execute("""
    ALTER TABLE medlm.extraction_revisions DROP CONSTRAINT extraction_metadata_complete,
      DROP COLUMN fixture_revision, DROP COLUMN sanitized_sha256, DROP COLUMN provider_id,
      DROP COLUMN model_id, DROP COLUMN pipeline_version;
    ALTER TABLE medlm.analysis_jobs DROP COLUMN safe_error_code;
    """)

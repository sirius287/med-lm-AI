"""Bounded synthetic lifecycle leases and expiry; no provider execution."""

from alembic import op
from sqlalchemy import text

revision = "0007_analysis_lifecycle"
down_revision = "0006_analysis_foundation"
branch_labels = None
depends_on = None

# Amend existing guard bodies without rewriting migration history. Exact matches
# fail closed if a deployment's prior function differs from the migration chain.
CHANGES = {
    "guard_analysis_parent": [
        ("-'cancelled_at'-'version'", "-'cancelled_at'-'version'-'expires_at'-'expired_at'"),
    ],
    "guard_analysis_child": [
        (
            "to_jsonb(NEW)-'state'",
            "to_jsonb(NEW)-'state'-'lease_token'-'lease_until'-'fencing_token'-'lifecycle_version'",
        ),
        (
            "to_jsonb(OLD)-'state'",
            "to_jsonb(OLD)-'state'-'lease_token'-'lease_until'-'fencing_token'-'lifecycle_version'",
        ),
        (
            "OR NEW.state=OLD.state",
            "OR (NEW.state=OLD.state AND NEW.lease_token IS NOT DISTINCT FROM OLD.lease_token)",
        ),
        (
            "IF NOT (NEW.state IN ('failed','cancelled')",
            "IF NEW.state IS DISTINCT FROM OLD.state AND NOT (NEW.state IN ('failed','cancelled')",
        ),
        ("(NEW.state='needs_input' AND OLD.state<>'queued')", "(NEW.state='needs_input')"),
    ],
}


def amend(reverse=False):
    for name, changes in CHANGES.items():
        definition = op.get_bind().scalar(
            text(f"SELECT pg_get_functiondef('medlm.{name}()'::regprocedure)")
        )
        for before, after in changes:
            source, target = (after, before) if reverse else (before, after)
            if source not in definition:
                raise RuntimeError(f"Unexpected prior guard: {name}")
            definition = definition.replace(source, target)
        op.execute(definition)


def upgrade():
    op.execute("""
    ALTER TABLE medlm.medicine_analyses
      ADD COLUMN expires_at timestamptz,
      ADD COLUMN expired_at timestamptz,
      ADD CONSTRAINT analysis_expiry_bounds CHECK(expires_at IS NULL OR
        (analysis_mode='synthetic' AND expires_at>created_at
         AND expires_at<=created_at+interval '24 hours')),
      ADD CONSTRAINT analysis_expired_marker CHECK(expired_at IS NULL OR
        (expires_at IS NOT NULL AND expired_at>=expires_at));
    ALTER TABLE medlm.analysis_jobs
      ADD COLUMN origin_session_id uuid,
      ADD COLUMN lease_token uuid,
      ADD COLUMN lease_until timestamptz,
      ADD COLUMN fencing_token bigint NOT NULL DEFAULT 0 CHECK(fencing_token>=0),
      ADD COLUMN lifecycle_version bigint NOT NULL DEFAULT 1 CHECK(lifecycle_version>0),
      ADD CONSTRAINT analysis_lease_pair CHECK((lease_token IS NULL)=(lease_until IS NULL));
    CREATE INDEX analysis_expiry_due ON medlm.medicine_analyses(user_id,expires_at)
      WHERE expires_at IS NOT NULL AND expired_at IS NULL AND cancelled_at IS NULL;
    CREATE INDEX analysis_lease_due ON medlm.analysis_jobs(user_id,lease_until)
      WHERE lease_until IS NOT NULL;
    CREATE FUNCTION medlm.guard_analysis_deadline() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP='INSERT' THEN
        IF NEW.expired_at IS NOT NULL THEN RAISE EXCEPTION 'Invalid expiry origin'; END IF;
      ELSE
        IF NEW.expires_at IS DISTINCT FROM OLD.expires_at
          THEN RAISE EXCEPTION 'Analysis deadline is immutable'; END IF;
        IF NEW.expired_at IS DISTINCT FROM OLD.expired_at THEN
          IF OLD.expired_at IS NOT NULL OR NEW.expired_at IS NULL
            OR NEW.expired_at>clock_timestamp() OR NEW.version<>OLD.version+1
            OR NEW.current_job_id IS DISTINCT FROM OLD.current_job_id
            OR NEW.current_revision_id IS DISTINCT FROM OLD.current_revision_id
            OR NEW.cancelled_at IS DISTINCT FROM OLD.cancelled_at
            THEN RAISE EXCEPTION 'Invalid expiry marker'; END IF;
        ELSIF OLD.expired_at IS NOT NULL THEN
          RAISE EXCEPTION 'Analysis has expired';
        END IF;
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER analysis_00_deadline BEFORE INSERT OR UPDATE ON medlm.medicine_analyses
      FOR EACH ROW EXECUTE FUNCTION medlm.guard_analysis_deadline();

    CREATE FUNCTION medlm.guard_analysis_lease() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE a medlm.medicine_analyses; j medlm.analysis_jobs; moment timestamptz;
    BEGIN
      SELECT * INTO a FROM medlm.medicine_analyses
        WHERE user_id=NEW.user_id AND id=NEW.analysis_id FOR UPDATE;
      IF a.expires_at IS NULL THEN
        IF TG_TABLE_NAME='analysis_jobs' THEN
          IF NEW.origin_session_id IS NOT NULL OR NEW.lease_token IS NOT NULL
            OR NEW.fencing_token<>0 OR NEW.lifecycle_version<>1
            THEN RAISE EXCEPTION 'Lifecycle requires a bounded analysis'; END IF;
        END IF;
        RETURN NEW;
      END IF;
      moment := clock_timestamp();
      IF a.expired_at IS NOT NULL OR a.expires_at<=moment OR a.cancelled_at IS NOT NULL
        THEN RAISE EXCEPTION 'Analysis unavailable'; END IF;
      PERFORM 1 FROM medlm.analysis_uploads l JOIN medlm.uploads u
        ON (u.user_id,u.id)=(l.user_id,l.upload_id)
        WHERE l.user_id=NEW.user_id AND l.analysis_id=NEW.analysis_id
          AND u.retain_for_review AND u.status='accepted' AND u.expires_at=a.expires_at
          AND u.expires_at>moment FOR SHARE OF u;
      IF NOT FOUND THEN RAISE EXCEPTION 'Retained upload unavailable'; END IF;
      IF TG_TABLE_NAME='analysis_jobs' AND TG_OP='INSERT' THEN
        IF NEW.origin_session_id IS NULL OR NEW.lease_token IS NOT NULL
          OR NEW.fencing_token<>0 OR NEW.lifecycle_version<>1
          THEN RAISE EXCEPTION 'Invalid lifecycle job origin'; END IF;
        RETURN NEW;
      END IF;
      IF TG_TABLE_NAME='analysis_jobs' THEN j := OLD;
      ELSE
        SELECT * INTO j FROM medlm.analysis_jobs
          WHERE user_id=NEW.user_id AND id=NEW.job_id FOR UPDATE;
      END IF;
      IF j.id IS DISTINCT FROM a.current_job_id
        OR j.origin_session_id IS DISTINCT FROM
          NULLIF(current_setting('app.analysis_session_id',true),'')::uuid
        THEN RAISE EXCEPTION 'Superseded job or session'; END IF;
      IF TG_TABLE_NAME='analysis_jobs' THEN
        IF NEW.lifecycle_version<>OLD.lifecycle_version+1
          THEN RAISE EXCEPTION 'Invalid job version'; END IF;
        IF NEW.state=OLD.state THEN
          IF OLD.state IN ('completed','failed','cancelled','needs_input')
            OR (OLD.lease_until IS NOT NULL AND OLD.lease_until>moment)
            OR NEW.lease_token IS NULL OR NEW.lease_token IS NOT DISTINCT FROM OLD.lease_token
            OR NEW.lease_until IS NULL OR NEW.lease_until<=moment
            OR NEW.lease_until>a.expires_at OR NEW.lease_until>moment+interval '60 seconds'
            OR NEW.fencing_token<>OLD.fencing_token+1
            THEN RAISE EXCEPTION 'Invalid lease acquisition'; END IF;
          RETURN NEW;
        END IF;
      END IF;
      IF j.lease_token IS NULL OR j.lease_until<=clock_timestamp()
        OR j.lease_token IS DISTINCT FROM
          NULLIF(current_setting('app.analysis_lease_token',true),'')::uuid
        OR j.fencing_token IS DISTINCT FROM
          NULLIF(current_setting('app.analysis_fence',true),'')::bigint
        THEN RAISE EXCEPTION 'Stale analysis lease'; END IF;
      IF TG_TABLE_NAME='analysis_jobs' THEN
        IF NEW.fencing_token<>OLD.fencing_token THEN RAISE EXCEPTION 'Invalid fence'; END IF;
        IF NEW.state IN ('completed','failed','cancelled','needs_input') THEN
          IF NEW.lease_token IS NOT NULL OR NEW.lease_until IS NOT NULL
            THEN RAISE EXCEPTION 'Terminal job must release lease'; END IF;
        ELSIF NEW.lease_token IS DISTINCT FROM OLD.lease_token
          OR NEW.lease_until IS DISTINCT FROM OLD.lease_until
          THEN RAISE EXCEPTION 'Transition cannot renew lease'; END IF;
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER analysis_00_lease BEFORE INSERT OR UPDATE ON medlm.analysis_jobs
      FOR EACH ROW EXECUTE FUNCTION medlm.guard_analysis_lease();
    CREATE TRIGGER analysis_00_publication_lease BEFORE INSERT ON medlm.extraction_revisions
      FOR EACH ROW EXECUTE FUNCTION medlm.guard_analysis_lease();
    REVOKE ALL ON FUNCTION medlm.guard_analysis_deadline(),medlm.guard_analysis_lease() FROM PUBLIC;
    """)
    amend()


def downgrade():
    op.execute("""
    ALTER TABLE medlm.medicine_analyses NO FORCE ROW LEVEL SECURITY;
    ALTER TABLE medlm.analysis_jobs NO FORCE ROW LEVEL SECURITY;
    DO $$ BEGIN IF EXISTS(SELECT 1 FROM medlm.medicine_analyses
      WHERE expires_at IS NOT NULL OR expired_at IS NOT NULL)
      OR EXISTS(SELECT 1 FROM medlm.analysis_jobs WHERE origin_session_id IS NOT NULL
        OR lease_token IS NOT NULL OR fencing_token<>0 OR lifecycle_version<>1)
      THEN RAISE EXCEPTION 'Lifecycle data exists; explicit export/erasure required'; END IF;
    END $$;
    ALTER TABLE medlm.medicine_analyses FORCE ROW LEVEL SECURITY;
    ALTER TABLE medlm.analysis_jobs FORCE ROW LEVEL SECURITY;
    DROP TRIGGER analysis_00_publication_lease ON medlm.extraction_revisions;
    DROP TRIGGER analysis_00_lease ON medlm.analysis_jobs;
    DROP TRIGGER analysis_00_deadline ON medlm.medicine_analyses;
    DROP FUNCTION medlm.guard_analysis_lease();
    DROP FUNCTION medlm.guard_analysis_deadline();
    DROP INDEX medlm.analysis_expiry_due;
    DROP INDEX medlm.analysis_lease_due;
    """)
    amend(reverse=True)
    op.execute("""
    ALTER TABLE medlm.analysis_jobs DROP COLUMN origin_session_id,DROP COLUMN lease_token,
      DROP COLUMN lease_until,DROP COLUMN fencing_token,DROP COLUMN lifecycle_version;
    ALTER TABLE medlm.medicine_analyses DROP COLUMN expires_at,DROP COLUMN expired_at;
    """)

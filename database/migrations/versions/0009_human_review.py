"""Version-bound synthetic human reviews; no clinical verification."""

from alembic import op

revision = "0009_human_review"
down_revision = "0008_synthetic_extraction"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    ALTER TABLE medlm.analysis_reviews DROP CONSTRAINT analysis_reviews_decision_check,
      ADD CONSTRAINT analysis_reviews_decision_check
        CHECK(decision IN ('confirm','correct','reject','unresolved')),
      ADD COLUMN review_schema_version int CHECK(review_schema_version=1),
      ADD COLUMN request_sha256 text CHECK(request_sha256 ~ '^[a-f0-9]{64}$'),
      ADD COLUMN line_dispositions jsonb,
      ADD CONSTRAINT managed_review_metadata CHECK (
        (review_schema_version IS NULL AND request_sha256 IS NULL AND line_dispositions IS NULL)
        OR (review_schema_version IS NOT NULL AND request_sha256 IS NOT NULL
          AND line_dispositions IS NOT NULL AND jsonb_typeof(line_dispositions)='object')),
      ADD CONSTRAINT unresolved_review_managed CHECK(decision<>'unresolved' OR
        (review_schema_version IS NOT NULL AND review_schema_version=1));
    CREATE UNIQUE INDEX managed_review_version ON medlm.analysis_reviews(user_id,analysis_id,analysis_version)
      WHERE review_schema_version=1;
    CREATE UNIQUE INDEX managed_final_review ON medlm.analysis_reviews(user_id,analysis_id)
      WHERE review_schema_version=1 AND decision<>'unresolved';
    ALTER TABLE medlm.analysis_prescription_lines ADD COLUMN source_line_id uuid;
    CREATE UNIQUE INDEX prescription_source_line ON medlm.analysis_prescription_lines
      (prescription_revision_id,source_line_id) WHERE source_line_id IS NOT NULL;

    CREATE FUNCTION medlm.guard_human_review() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE a medlm.medicine_analyses;
    BEGIN
      SELECT * INTO a FROM medlm.medicine_analyses
        WHERE user_id=NEW.user_id AND id=NEW.analysis_id FOR UPDATE;
      IF a.expires_at IS NULL THEN RETURN NEW; END IF;
      IF a.expired_at IS NOT NULL OR a.expires_at<=clock_timestamp() OR a.cancelled_at IS NOT NULL
        THEN RAISE EXCEPTION 'Review unavailable'; END IF;
      IF EXISTS(SELECT 1 FROM medlm.analysis_reviews WHERE user_id=a.user_id AND analysis_id=a.id
        AND review_schema_version=1 AND decision<>'unresolved')
        THEN RAISE EXCEPTION 'Review is closed'; END IF;
      PERFORM 1 FROM medlm.analysis_uploads l JOIN medlm.uploads u
        ON (u.user_id,u.id)=(l.user_id,l.upload_id)
        WHERE l.user_id=a.user_id AND l.analysis_id=a.id AND u.retain_for_review
          AND u.status='accepted' AND u.expires_at=a.expires_at AND u.expires_at>clock_timestamp();
      IF NOT FOUND THEN RAISE EXCEPTION 'Review image unavailable'; END IF;
      IF TG_TABLE_NAME='analysis_reviews' THEN
        IF NEW.review_schema_version IS DISTINCT FROM 1 OR NEW.candidate_id IS NOT NULL
          OR EXISTS(SELECT 1 FROM medlm.identity_candidates WHERE candidate_set_id=NEW.candidate_set_id)
          THEN RAISE EXCEPTION 'Managed empty candidate review required'; END IF;
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER human_review_guard BEFORE INSERT ON medlm.analysis_reviews
      FOR EACH ROW EXECUTE FUNCTION medlm.guard_human_review();
    CREATE TRIGGER human_candidate_guard BEFORE INSERT ON medlm.identity_candidate_sets
      FOR EACH ROW EXECUTE FUNCTION medlm.guard_human_review();
    CREATE TRIGGER human_prescription_guard BEFORE INSERT ON medlm.analysis_prescription_revisions
      FOR EACH ROW EXECUTE FUNCTION medlm.guard_human_review();
    CREATE TRIGGER human_confirmation_guard BEFORE INSERT ON medlm.analysis_prescription_confirmations
      FOR EACH ROW EXECUTE FUNCTION medlm.guard_human_review();

    CREATE FUNCTION medlm.guard_closed_review() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF (NEW.current_job_id IS DISTINCT FROM OLD.current_job_id
        OR NEW.current_revision_id IS DISTINCT FROM OLD.current_revision_id)
        AND EXISTS(SELECT 1 FROM medlm.analysis_reviews WHERE user_id=OLD.user_id
          AND analysis_id=OLD.id AND review_schema_version=1 AND decision<>'unresolved')
        THEN RAISE EXCEPTION 'Final review cannot reopen'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER closed_review_guard BEFORE UPDATE ON medlm.medicine_analyses
      FOR EACH ROW EXECUTE FUNCTION medlm.guard_closed_review();
    CREATE FUNCTION medlm.check_human_review_commit() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.review_schema_version=1 AND EXISTS(SELECT 1 FROM medlm.analysis_reviews WHERE id=NEW.id) THEN
        IF NOT EXISTS(SELECT 1 FROM medlm.medicine_analyses WHERE user_id=NEW.user_id
          AND id=NEW.analysis_id AND version>NEW.analysis_version)
          THEN RAISE EXCEPTION 'Review must consume analysis version'; END IF;
        IF NEW.decision<>'unresolved' AND EXISTS(
          SELECT 1 FROM medlm.analysis_uploads l JOIN medlm.uploads u
            ON (u.user_id,u.id)=(l.user_id,l.upload_id)
            WHERE l.user_id=NEW.user_id AND l.analysis_id=NEW.analysis_id
              AND (u.status NOT IN ('deleting','deleted') OR EXISTS(
                SELECT 1 FROM medlm.upload_objects o WHERE o.user_id=u.user_id AND o.upload_id=u.id
                  AND o.purged_at IS NULL AND NOT EXISTS(SELECT 1 FROM medlm.upload_deletion_jobs d
                    WHERE d.user_id=o.user_id AND d.object_id=o.id))))
          THEN RAISE EXCEPTION 'Final review must queue deletion'; END IF;
      END IF;
      RETURN NULL;
    END $$;
    CREATE CONSTRAINT TRIGGER human_review_atomic AFTER INSERT ON medlm.analysis_reviews
      DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION medlm.check_human_review_commit();
    CREATE FUNCTION medlm.check_human_confirmation() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF EXISTS(SELECT 1 FROM medlm.analysis_prescription_confirmations WHERE id=NEW.id)
        AND EXISTS(SELECT 1 FROM medlm.medicine_analyses WHERE id=NEW.analysis_id AND expires_at IS NOT NULL)
        AND NOT EXISTS(SELECT 1 FROM medlm.analysis_reviews r JOIN medlm.analysis_prescription_revisions p
          ON (p.user_id,p.analysis_id,p.extraction_revision_id)=(r.user_id,r.analysis_id,r.extraction_revision_id)
          WHERE r.user_id=NEW.user_id AND r.analysis_id=NEW.analysis_id AND p.id=NEW.prescription_revision_id
            AND r.analysis_version=NEW.analysis_version AND r.review_schema_version=1
            AND r.decision<>'unresolved')
        THEN RAISE EXCEPTION 'Prescription confirmation requires final human review'; END IF;
      RETURN NULL;
    END $$;
    CREATE CONSTRAINT TRIGGER human_confirmation_atomic AFTER INSERT ON medlm.analysis_prescription_confirmations
      DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION medlm.check_human_confirmation();
    REVOKE ALL ON FUNCTION medlm.guard_human_review(),medlm.guard_closed_review(),
      medlm.check_human_review_commit(),medlm.check_human_confirmation() FROM PUBLIC;
    """)


def downgrade():
    op.execute("""
    ALTER TABLE medlm.analysis_reviews NO FORCE ROW LEVEL SECURITY;
    ALTER TABLE medlm.analysis_prescription_lines NO FORCE ROW LEVEL SECURITY;
    DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM medlm.analysis_reviews WHERE review_schema_version IS NOT NULL
          OR decision='unresolved')
        OR EXISTS(SELECT 1 FROM medlm.analysis_prescription_lines WHERE source_line_id IS NOT NULL)
        THEN RAISE EXCEPTION 'Human review data exists; explicit export/erasure required'; END IF;
    END $$;
    ALTER TABLE medlm.analysis_reviews FORCE ROW LEVEL SECURITY;
    ALTER TABLE medlm.analysis_prescription_lines FORCE ROW LEVEL SECURITY;
    DROP TRIGGER human_review_atomic ON medlm.analysis_reviews;
    DROP TRIGGER human_confirmation_atomic ON medlm.analysis_prescription_confirmations;
    DROP TRIGGER human_review_guard ON medlm.analysis_reviews;
    DROP TRIGGER human_candidate_guard ON medlm.identity_candidate_sets;
    DROP TRIGGER human_prescription_guard ON medlm.analysis_prescription_revisions;
    DROP TRIGGER human_confirmation_guard ON medlm.analysis_prescription_confirmations;
    DROP TRIGGER closed_review_guard ON medlm.medicine_analyses;
    DROP FUNCTION medlm.guard_human_review();
    DROP FUNCTION medlm.guard_closed_review();
    DROP FUNCTION medlm.check_human_review_commit();
    DROP FUNCTION medlm.check_human_confirmation();
    DROP INDEX medlm.managed_review_version;
    DROP INDEX medlm.managed_final_review;
    DROP INDEX medlm.prescription_source_line;
    ALTER TABLE medlm.analysis_prescription_lines DROP COLUMN source_line_id;
    ALTER TABLE medlm.analysis_reviews DROP CONSTRAINT managed_review_metadata,
      DROP CONSTRAINT unresolved_review_managed, DROP COLUMN review_schema_version,
      DROP COLUMN request_sha256, DROP COLUMN line_dispositions,
      DROP CONSTRAINT analysis_reviews_decision_check,
      ADD CONSTRAINT analysis_reviews_decision_check CHECK(decision IN ('confirm','correct','reject'));
    """)

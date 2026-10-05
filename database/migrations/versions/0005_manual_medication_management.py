"""Additive manual-management schema; no activation or inferred legacy data."""

from alembic import op

revision = "0005_manual_medications"
down_revision = "0004_upload_runtime"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
      CREATE TABLE medlm.medication_instruction_revisions (
        id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES medlm.users(id) ON DELETE CASCADE,
        medication_id uuid NOT NULL, revision int NOT NULL CHECK(revision>0),
        fields jsonb NOT NULL, origin text NOT NULL CHECK(origin IN ('manual','confirmed_prescription')),
        reviewed_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE(user_id,id), UNIQUE(user_id,medication_id,id), UNIQUE(medication_id,revision),
        FOREIGN KEY(user_id,medication_id) REFERENCES medlm.medications(user_id,id) ON DELETE CASCADE
      );
      ALTER TABLE medlm.medications ADD COLUMN updated_at timestamptz,
        ADD COLUMN current_instruction_id uuid,
        ADD CONSTRAINT medication_instruction_owner FOREIGN KEY(user_id,id,current_instruction_id)
          REFERENCES medlm.medication_instruction_revisions(user_id,medication_id,id)
          DEFERRABLE INITIALLY DEFERRED;
      ALTER TABLE medlm.medication_schedules ADD COLUMN effective_at timestamptz,
        ADD COLUMN instruction_revision_id uuid,
        ADD CONSTRAINT schedule_instruction_owner FOREIGN KEY(user_id,medication_id,instruction_revision_id)
          REFERENCES medlm.medication_instruction_revisions(user_id,medication_id,id)
          DEFERRABLE INITIALLY DEFERRED;
      ALTER TABLE medlm.dose_occurrences ADD COLUMN original_local_time text;
      ALTER TABLE medlm.dose_events ADD COLUMN supersedes_event_id uuid,
        ADD COLUMN occurrence_version int CHECK(occurrence_version>0),
        ADD CONSTRAINT dose_event_version UNIQUE(occurrence_id,occurrence_version),
        ADD CONSTRAINT dose_event_correction_owner FOREIGN KEY(user_id,supersedes_event_id)
          REFERENCES medlm.dose_events(user_id,id) DEFERRABLE INITIALLY DEFERRED;
      CREATE TABLE medlm.idempotency_records (
        user_id uuid NOT NULL REFERENCES medlm.users(id) ON DELETE CASCADE,
        operation text NOT NULL, key uuid NOT NULL, request_hash text NOT NULL,
        encrypted_response text NOT NULL, resource_id uuid, invalidated boolean NOT NULL DEFAULT false,
        expires_at timestamptz NOT NULL DEFAULT now()+interval '24 hours',
        PRIMARY KEY(user_id,operation,key)
      );
      CREATE INDEX ON medlm.idempotency_records(expires_at);
      CREATE INDEX ON medlm.idempotency_records(user_id,resource_id);
      CREATE INDEX manual_medication_order ON medlm.medications(user_id,created_at,id);
      CREATE INDEX ON medlm.medication_instruction_revisions(user_id,medication_id);
      CREATE INDEX manual_schedule_owner ON medlm.medication_schedules(user_id,medication_id);
      CREATE INDEX manual_event_order ON medlm.dose_events(user_id,occurrence_id,recorded_at,id);
      CREATE FUNCTION medlm.reject_manual_history_update() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN RAISE EXCEPTION 'History is immutable'; END $$;
      CREATE TRIGGER instruction_immutable BEFORE UPDATE ON medlm.medication_instruction_revisions
        FOR EACH ROW EXECUTE FUNCTION medlm.reject_manual_history_update();
      CREATE TRIGGER dose_event_immutable BEFORE UPDATE ON medlm.dose_events
        FOR EACH ROW EXECUTE FUNCTION medlm.reject_manual_history_update();
      CREATE FUNCTION medlm.check_schedule_revision_update() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF (to_jsonb(NEW)-'retired_at') IS DISTINCT FROM (to_jsonb(OLD)-'retired_at')
          OR OLD.retired_at IS NOT NULL THEN RAISE EXCEPTION 'Schedule revision is immutable'; END IF;
        RETURN NEW;
      END $$;
      CREATE TRIGGER schedule_immutable BEFORE UPDATE ON medlm.medication_schedules
        FOR EACH ROW EXECUTE FUNCTION medlm.check_schedule_revision_update();
      CREATE FUNCTION medlm.check_occurrence_update() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF (to_jsonb(NEW)-'status'-'version') IS DISTINCT FROM (to_jsonb(OLD)-'status'-'version')
          THEN RAISE EXCEPTION 'Dose context is immutable'; END IF;
        RETURN NEW;
      END $$;
      CREATE TRIGGER occurrence_context_immutable BEFORE UPDATE ON medlm.dose_occurrences
        FOR EACH ROW EXECUTE FUNCTION medlm.check_occurrence_update();
    """)
    for table in ("medication_instruction_revisions", "idempotency_records"):
        op.execute(f"ALTER TABLE medlm.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE medlm.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY owner_access ON medlm.{table}
          USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)
          WITH CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)""")
        op.execute(f"REVOKE ALL ON medlm.{table} FROM PUBLIC")
    op.execute("""CREATE POLICY expiry_maintenance ON medlm.idempotency_records
      USING(current_user='medlm_medication_maintenance' AND expires_at<=now())""")


def downgrade():
    # Never silently discard new instruction/audit history during rollback.
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM medlm.medication_instruction_revisions)
        OR EXISTS(SELECT 1 FROM medlm.idempotency_records)
      THEN RAISE EXCEPTION 'Manual data exists; downgrade requires explicit export/erasure'; END IF;
    END $$;
    DROP TRIGGER occurrence_context_immutable ON medlm.dose_occurrences;
    DROP FUNCTION medlm.check_occurrence_update();
    DROP TRIGGER schedule_immutable ON medlm.medication_schedules;
    DROP FUNCTION medlm.check_schedule_revision_update();
    DROP TRIGGER dose_event_immutable ON medlm.dose_events;
    DROP TRIGGER instruction_immutable ON medlm.medication_instruction_revisions;
    DROP FUNCTION medlm.reject_manual_history_update();
    DROP INDEX medlm.manual_medication_order;
    DROP INDEX medlm.manual_schedule_owner;
    DROP INDEX medlm.manual_event_order;
    ALTER TABLE medlm.dose_events DROP COLUMN supersedes_event_id, DROP COLUMN occurrence_version;
    ALTER TABLE medlm.dose_occurrences DROP COLUMN original_local_time;
    ALTER TABLE medlm.medication_schedules DROP COLUMN effective_at, DROP COLUMN instruction_revision_id;
    ALTER TABLE medlm.medications DROP COLUMN updated_at, DROP COLUMN current_instruction_id;
    DROP TABLE medlm.medication_instruction_revisions;
    DROP TABLE medlm.idempotency_records;
    """)

"""Synthetic analysis persistence only; no execution, routes or clinical enablement."""

from alembic import op

revision = "0006_analysis_foundation"
down_revision = "0005_manual_medications"
branch_labels = None
depends_on = None

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


def upgrade():
    op.execute("""
    ALTER TABLE medlm.medicine_analyses
      ADD COLUMN analysis_mode text CHECK(analysis_mode='synthetic'),
      ADD COLUMN current_job_id uuid,
      ADD COLUMN current_revision_id uuid,
      ADD COLUMN cancelled_at timestamptz;
    ALTER TABLE medlm.prescriptions ADD CONSTRAINT prescription_analysis_owner
      UNIQUE(user_id,id,analysis_id);

    CREATE TABLE medlm.analysis_uploads (
      id uuid PRIMARY KEY, user_id uuid NOT NULL,
      analysis_id uuid NOT NULL, upload_id uuid NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(user_id,id), UNIQUE(analysis_id), UNIQUE(upload_id),
      FOREIGN KEY(user_id,analysis_id) REFERENCES medlm.medicine_analyses(user_id,id)
        ON DELETE CASCADE,
      FOREIGN KEY(user_id,upload_id) REFERENCES medlm.uploads(user_id,id) ON DELETE CASCADE
    );
    CREATE TABLE medlm.analysis_jobs (
      id uuid PRIMARY KEY, user_id uuid NOT NULL, analysis_id uuid NOT NULL,
      attempt int NOT NULL CHECK(attempt>0), request_key uuid NOT NULL,
      state text NOT NULL DEFAULT 'queued' CHECK(state IN
        ('queued','validating','extracting','retrieving','validating_output',
         'completed','needs_input','failed','cancelled')),
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(user_id,id), UNIQUE(user_id,analysis_id,id),
      UNIQUE(analysis_id,attempt), UNIQUE(user_id,analysis_id,request_key),
      FOREIGN KEY(user_id,analysis_id) REFERENCES medlm.medicine_analyses(user_id,id)
        ON DELETE CASCADE
    );
    CREATE TABLE medlm.extraction_revisions (
      id uuid PRIMARY KEY, user_id uuid NOT NULL, analysis_id uuid NOT NULL,
      job_id uuid NOT NULL, revision int NOT NULL CHECK(revision>0),
      observations jsonb NOT NULL CHECK(jsonb_typeof(observations)='object'),
      contract_version int NOT NULL DEFAULT 1 CHECK(contract_version=1),
      fixture_id text NOT NULL CHECK(length(fixture_id) BETWEEN 1 AND 160),
      fixture_sha256 text NOT NULL CHECK(fixture_sha256 ~ '^[a-f0-9]{64}$'),
      provenance text NOT NULL DEFAULT 'synthetic' CHECK(provenance='synthetic'),
      verification text NOT NULL DEFAULT 'unverified'
        CHECK(verification IN ('unverified','ambiguous','unsupported_market')),
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(user_id,id), UNIQUE(user_id,analysis_id,id), UNIQUE(analysis_id,revision),
      UNIQUE(job_id),
      FOREIGN KEY(user_id,analysis_id,job_id)
        REFERENCES medlm.analysis_jobs(user_id,analysis_id,id) ON DELETE CASCADE
    );
    ALTER TABLE medlm.medicine_analyses
      ADD CONSTRAINT analysis_current_job_owner FOREIGN KEY(user_id,id,current_job_id)
        REFERENCES medlm.analysis_jobs(user_id,analysis_id,id) DEFERRABLE INITIALLY DEFERRED,
      ADD CONSTRAINT analysis_current_revision_owner FOREIGN KEY(user_id,id,current_revision_id)
        REFERENCES medlm.extraction_revisions(user_id,analysis_id,id)
        DEFERRABLE INITIALLY DEFERRED;
    CREATE TABLE medlm.identity_candidate_sets (
      id uuid PRIMARY KEY, user_id uuid NOT NULL, analysis_id uuid NOT NULL,
      extraction_revision_id uuid NOT NULL,
      assembly_transaction xid8 NOT NULL DEFAULT pg_current_xact_id(),
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(user_id,id), UNIQUE(extraction_revision_id),
      UNIQUE(user_id,analysis_id,extraction_revision_id,id),
      FOREIGN KEY(user_id,analysis_id,extraction_revision_id)
        REFERENCES medlm.extraction_revisions(user_id,analysis_id,id) ON DELETE CASCADE
    );
    CREATE TABLE medlm.identity_candidates (
      id uuid PRIMARY KEY, user_id uuid NOT NULL, analysis_id uuid NOT NULL,
      extraction_revision_id uuid NOT NULL, candidate_set_id uuid NOT NULL,
      ordinal int NOT NULL CHECK(ordinal>=0),
      observed_name text NOT NULL CHECK(length(observed_name) BETWEEN 1 AND 1000),
      UNIQUE(user_id,id), UNIQUE(candidate_set_id,ordinal),
      UNIQUE(user_id,candidate_set_id,id),
      FOREIGN KEY(user_id,analysis_id,extraction_revision_id,candidate_set_id)
        REFERENCES medlm.identity_candidate_sets(user_id,analysis_id,extraction_revision_id,id)
        ON DELETE CASCADE
    );
    CREATE TABLE medlm.analysis_reviews (
      id uuid PRIMARY KEY, user_id uuid NOT NULL, analysis_id uuid NOT NULL,
      extraction_revision_id uuid NOT NULL, candidate_set_id uuid NOT NULL,
      candidate_id uuid, request_key uuid NOT NULL,
      analysis_version int NOT NULL CHECK(analysis_version>0),
      decision text NOT NULL CHECK(decision IN ('confirm','correct','reject')),
      fields jsonb NOT NULL CHECK(jsonb_typeof(fields)='object' AND fields<>'{}'::jsonb),
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(user_id,id), UNIQUE(user_id,analysis_id,request_key),
      FOREIGN KEY(user_id,analysis_id,extraction_revision_id,candidate_set_id)
        REFERENCES medlm.identity_candidate_sets(user_id,analysis_id,extraction_revision_id,id)
        ON DELETE CASCADE,
      FOREIGN KEY(user_id,candidate_set_id,candidate_id)
        REFERENCES medlm.identity_candidates(user_id,candidate_set_id,id)
    );
    CREATE TABLE medlm.analysis_prescription_drafts (
      id uuid PRIMARY KEY, user_id uuid NOT NULL, analysis_id uuid NOT NULL,
      prescription_id uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(user_id,id), UNIQUE(analysis_id), UNIQUE(prescription_id),
      UNIQUE(user_id,analysis_id,id),
      FOREIGN KEY(user_id,analysis_id) REFERENCES medlm.medicine_analyses(user_id,id)
        ON DELETE CASCADE,
      FOREIGN KEY(user_id,prescription_id,analysis_id)
        REFERENCES medlm.prescriptions(user_id,id,analysis_id) ON DELETE CASCADE
    );
    CREATE TABLE medlm.analysis_prescription_revisions (
      id uuid PRIMARY KEY, user_id uuid NOT NULL, analysis_id uuid NOT NULL,
      draft_id uuid NOT NULL, extraction_revision_id uuid NOT NULL,
      revision int NOT NULL CHECK(revision>0), created_at timestamptz NOT NULL DEFAULT now(),
      assembly_transaction xid8 NOT NULL DEFAULT pg_current_xact_id(),
      UNIQUE(user_id,id), UNIQUE(draft_id,revision), UNIQUE(draft_id,extraction_revision_id),
      UNIQUE(user_id,analysis_id,draft_id,id),
      FOREIGN KEY(user_id,analysis_id,draft_id)
        REFERENCES medlm.analysis_prescription_drafts(user_id,analysis_id,id) ON DELETE CASCADE,
      FOREIGN KEY(user_id,analysis_id,extraction_revision_id)
        REFERENCES medlm.extraction_revisions(user_id,analysis_id,id) ON DELETE CASCADE
    );
    CREATE TABLE medlm.analysis_prescription_lines (
      id uuid PRIMARY KEY, user_id uuid NOT NULL, analysis_id uuid NOT NULL,
      draft_id uuid NOT NULL, prescription_revision_id uuid NOT NULL,
      ordinal int NOT NULL CHECK(ordinal>=0),
      fields jsonb NOT NULL CHECK(jsonb_typeof(fields)='object'),
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(user_id,id), UNIQUE(prescription_revision_id,ordinal),
      UNIQUE(user_id,analysis_id,draft_id,prescription_revision_id,id),
      FOREIGN KEY(user_id,analysis_id,draft_id,prescription_revision_id)
        REFERENCES medlm.analysis_prescription_revisions(user_id,analysis_id,draft_id,id)
        ON DELETE CASCADE
    );
    CREATE TABLE medlm.analysis_prescription_confirmations (
      id uuid PRIMARY KEY, user_id uuid NOT NULL, analysis_id uuid NOT NULL,
      draft_id uuid NOT NULL, prescription_revision_id uuid NOT NULL,
      request_key uuid NOT NULL, analysis_version int NOT NULL CHECK(analysis_version>0),
      assembly_transaction xid8 NOT NULL DEFAULT pg_current_xact_id(),
      reviewed_fields jsonb NOT NULL CHECK(jsonb_typeof(reviewed_fields)='object'
        AND reviewed_fields<>'{}'::jsonb),
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(user_id,id), UNIQUE(prescription_revision_id),
      UNIQUE(user_id,analysis_id,draft_id,prescription_revision_id,id),
      UNIQUE(user_id,analysis_id,request_key),
      FOREIGN KEY(user_id,analysis_id,draft_id,prescription_revision_id)
        REFERENCES medlm.analysis_prescription_revisions(user_id,analysis_id,draft_id,id)
        ON DELETE CASCADE
    );
    CREATE TABLE medlm.analysis_prescription_confirmation_lines (
      id uuid PRIMARY KEY, user_id uuid NOT NULL, analysis_id uuid NOT NULL,
      draft_id uuid NOT NULL, prescription_revision_id uuid NOT NULL,
      confirmation_id uuid NOT NULL, line_id uuid NOT NULL,
      disposition text NOT NULL CHECK(disposition IN ('included','excluded','unresolved')),
      reviewed_fields jsonb NOT NULL CHECK(jsonb_typeof(reviewed_fields)='object'),
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(user_id,id), UNIQUE(confirmation_id,line_id),
      FOREIGN KEY(user_id,analysis_id,draft_id,prescription_revision_id,confirmation_id)
        REFERENCES medlm.analysis_prescription_confirmations
          (user_id,analysis_id,draft_id,prescription_revision_id,id) ON DELETE CASCADE,
      FOREIGN KEY(user_id,analysis_id,draft_id,prescription_revision_id,line_id)
        REFERENCES medlm.analysis_prescription_lines
          (user_id,analysis_id,draft_id,prescription_revision_id,id) ON DELETE CASCADE
    );
    CREATE INDEX analysis_upload_lookup ON medlm.analysis_uploads(user_id,upload_id);
    CREATE INDEX analysis_job_order ON medlm.analysis_jobs(user_id,analysis_id,attempt);
    CREATE INDEX analysis_revision_order ON medlm.extraction_revisions(user_id,analysis_id,revision);
    CREATE INDEX analysis_review_order ON medlm.analysis_reviews(user_id,analysis_id,created_at,id);

    CREATE FUNCTION medlm.guard_analysis_parent() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE j medlm.analysis_jobs; r medlm.extraction_revisions; old_attempt int;
    BEGIN
      IF TG_OP='INSERT' THEN
        IF NEW.analysis_mode='synthetic' AND (NEW.current_job_id IS NOT NULL
          OR NEW.current_revision_id IS NOT NULL OR NEW.version<>1 OR NEW.state<>'queued'
          OR NEW.cancelled_at IS NOT NULL) THEN RAISE EXCEPTION 'Invalid analysis origin'; END IF;
        RETURN NEW;
      END IF;
      IF OLD.analysis_mode IS NULL AND NEW.analysis_mode IS NULL THEN RETURN NEW; END IF;
      IF OLD.analysis_mode IS DISTINCT FROM NEW.analysis_mode OR
        (to_jsonb(NEW)-'current_job_id'-'current_revision_id'-'cancelled_at'-'version')
          IS DISTINCT FROM
        (to_jsonb(OLD)-'current_job_id'-'current_revision_id'-'cancelled_at'-'version')
        OR OLD.cancelled_at IS NOT NULL OR NEW.version<>OLD.version+1
        THEN RAISE EXCEPTION 'Invalid stable analysis update'; END IF;
      IF NEW.cancelled_at IS NOT NULL AND (NEW.current_job_id IS DISTINCT FROM OLD.current_job_id
        OR NEW.current_revision_id IS DISTINCT FROM OLD.current_revision_id)
        THEN RAISE EXCEPTION 'Cancellation cannot publish'; END IF;
      IF NEW.current_job_id IS DISTINCT FROM OLD.current_job_id THEN
        SELECT * INTO j FROM medlm.analysis_jobs WHERE user_id=NEW.user_id
          AND analysis_id=NEW.id AND id=NEW.current_job_id;
        SELECT attempt INTO old_attempt FROM medlm.analysis_jobs WHERE id=OLD.current_job_id;
        IF j.id IS NULL OR j.state<>'queued' OR j.attempt<>COALESCE(old_attempt,0)+1
          OR NEW.current_revision_id IS DISTINCT FROM OLD.current_revision_id
          THEN RAISE EXCEPTION 'Invalid current job'; END IF;
      END IF;
      IF NEW.current_revision_id IS DISTINCT FROM OLD.current_revision_id THEN
        SELECT * INTO r FROM medlm.extraction_revisions WHERE user_id=NEW.user_id
          AND analysis_id=NEW.id AND id=NEW.current_revision_id;
        IF r.id IS NULL OR r.job_id IS DISTINCT FROM NEW.current_job_id
          OR NOT EXISTS(SELECT 1 FROM medlm.analysis_jobs
            WHERE id=NEW.current_job_id AND state='validating_output')
          OR r.revision<>COALESCE((SELECT revision FROM medlm.extraction_revisions
             WHERE id=OLD.current_revision_id),0)+1
          THEN RAISE EXCEPTION 'Stale extraction publication'; END IF;
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER stable_analysis_guard BEFORE INSERT OR UPDATE ON medlm.medicine_analyses
      FOR EACH ROW EXECUTE FUNCTION medlm.guard_analysis_parent();

    CREATE FUNCTION medlm.guard_analysis_child() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE a medlm.medicine_analyses; j medlm.analysis_jobs; expected int; target uuid;
    BEGIN
      SELECT * INTO a FROM medlm.medicine_analyses
        WHERE user_id=NEW.user_id AND id=NEW.analysis_id FOR UPDATE;
      IF a.id IS NULL OR a.analysis_mode IS DISTINCT FROM 'synthetic' OR a.cancelled_at IS NOT NULL
        THEN RAISE EXCEPTION 'Analysis unavailable'; END IF;
      IF TG_TABLE_NAME='analysis_uploads' THEN
        PERFORM 1 FROM medlm.uploads WHERE user_id=NEW.user_id AND id=NEW.upload_id
          AND retain_for_review AND status='accepted' AND expires_at>now() FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Retained synthetic upload required'; END IF;
      ELSIF TG_TABLE_NAME='analysis_jobs' THEN
        IF TG_OP='INSERT' THEN
          SELECT COALESCE(max(attempt),0)+1 INTO expected FROM medlm.analysis_jobs
            WHERE user_id=NEW.user_id AND analysis_id=NEW.analysis_id;
          IF NEW.attempt<>expected OR NEW.state<>'queued'
            THEN RAISE EXCEPTION 'Invalid job origin'; END IF;
        ELSE
          IF (to_jsonb(NEW)-'state') IS DISTINCT FROM (to_jsonb(OLD)-'state')
            OR OLD.state IN ('completed','needs_input','failed','cancelled')
            OR a.current_job_id IS DISTINCT FROM NEW.id OR NEW.state=OLD.state
            THEN RAISE EXCEPTION 'Job is immutable or superseded'; END IF;
          IF NOT (NEW.state IN ('failed','cancelled')
            OR (NEW.state='needs_input' AND OLD.state<>'queued')
            OR (OLD.state,NEW.state) IN (('queued','validating'),('validating','extracting'),
              ('extracting','retrieving'),('retrieving','validating_output'),
              ('validating_output','completed')))
            THEN RAISE EXCEPTION 'Invalid job transition'; END IF;
          IF NEW.state='completed' AND NOT EXISTS(SELECT 1 FROM medlm.extraction_revisions
            WHERE id=a.current_revision_id AND job_id=NEW.id)
            THEN RAISE EXCEPTION 'Completion requires published extraction'; END IF;
        END IF;
      ELSIF TG_TABLE_NAME='extraction_revisions' THEN
        SELECT * INTO j FROM medlm.analysis_jobs WHERE user_id=NEW.user_id AND id=NEW.job_id;
        SELECT COALESCE(max(revision),0)+1 INTO expected FROM medlm.extraction_revisions
          WHERE user_id=NEW.user_id AND analysis_id=NEW.analysis_id;
        IF j.id IS DISTINCT FROM a.current_job_id OR j.state<>'validating_output'
          OR NEW.revision<>expected THEN RAISE EXCEPTION 'Stale or invalid extraction'; END IF;
      ELSIF TG_TABLE_NAME='analysis_prescription_drafts' THEN
        IF a.kind<>'prescription' THEN RAISE EXCEPTION 'Prescription analysis required'; END IF;
      ELSE
        IF TG_TABLE_NAME IN ('identity_candidate_sets','analysis_prescription_revisions',
          'analysis_prescription_confirmations') THEN
          NEW.assembly_transaction := pg_current_xact_id();
        END IF;
        IF TG_TABLE_NAME='identity_candidates' THEN
          IF NOT EXISTS(
          SELECT 1 FROM medlm.identity_candidate_sets WHERE id=NEW.candidate_set_id
          AND assembly_transaction=pg_current_xact_id())
          THEN RAISE EXCEPTION 'Candidate set assembly is sealed'; END IF;
        END IF;
        IF TG_TABLE_NAME='analysis_prescription_lines' THEN
          IF NOT EXISTS(
          SELECT 1 FROM medlm.analysis_prescription_revisions WHERE id=NEW.prescription_revision_id
          AND assembly_transaction=pg_current_xact_id())
          THEN RAISE EXCEPTION 'Prescription revision assembly is sealed'; END IF;
        END IF;
        IF TG_TABLE_NAME='analysis_prescription_confirmation_lines' THEN
          IF NOT EXISTS(SELECT 1 FROM medlm.analysis_prescription_confirmations
            WHERE user_id=NEW.user_id AND id=NEW.confirmation_id
              AND assembly_transaction=pg_current_xact_id() AND analysis_version=a.version)
            THEN RAISE EXCEPTION 'Confirmation assembly is sealed or stale'; END IF;
        END IF;
        IF TG_TABLE_NAME IN ('analysis_prescription_lines','analysis_prescription_confirmations',
          'analysis_prescription_confirmation_lines') THEN
          SELECT extraction_revision_id INTO target FROM medlm.analysis_prescription_revisions
            WHERE user_id=NEW.user_id AND id=NEW.prescription_revision_id;
        ELSE target := NEW.extraction_revision_id; END IF;
        IF target IS DISTINCT FROM a.current_revision_id OR NOT EXISTS(
          SELECT 1 FROM medlm.extraction_revisions er JOIN medlm.analysis_jobs aj ON aj.id=er.job_id
          WHERE er.id=target AND er.job_id=a.current_job_id AND aj.state='completed')
          THEN RAISE EXCEPTION 'Current completed revision required'; END IF;
        IF TG_TABLE_NAME IN ('analysis_reviews','analysis_prescription_confirmations') THEN
          IF NEW.analysis_version<>a.version THEN RAISE EXCEPTION 'Stale review'; END IF;
        END IF;
        IF TG_TABLE_NAME='analysis_prescription_revisions' THEN
          SELECT COALESCE(max(revision),0)+1 INTO expected
            FROM medlm.analysis_prescription_revisions WHERE draft_id=NEW.draft_id;
          IF NEW.revision<>expected THEN RAISE EXCEPTION 'Invalid prescription revision'; END IF;
        END IF;
        IF TG_TABLE_NAME='analysis_prescription_lines' THEN
          IF EXISTS(
          SELECT 1 FROM medlm.analysis_prescription_confirmations
          WHERE prescription_revision_id=NEW.prescription_revision_id)
          THEN RAISE EXCEPTION 'Confirmed lines are sealed'; END IF;
        END IF;
        IF TG_TABLE_NAME='analysis_prescription_confirmations' THEN
          IF NOT EXISTS(
          SELECT 1 FROM medlm.analysis_prescription_lines
          WHERE prescription_revision_id=NEW.prescription_revision_id)
          THEN RAISE EXCEPTION 'Empty prescription cannot be confirmed'; END IF;
        END IF;
        IF TG_TABLE_NAME='identity_candidates' THEN
          IF EXISTS(
          SELECT 1 FROM medlm.analysis_reviews WHERE candidate_set_id=NEW.candidate_set_id)
          THEN RAISE EXCEPTION 'Reviewed candidates are sealed'; END IF;
        END IF;
      END IF;
      RETURN NEW;
    END $$;
    CREATE FUNCTION medlm.reject_analysis_history_update() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Analysis history is immutable'; END $$;
    CREATE FUNCTION medlm.check_extraction_publication() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      -- Erasure in this transaction is allowed; otherwise publication must be atomic.
      IF EXISTS(SELECT 1 FROM medlm.extraction_revisions WHERE id=NEW.id) AND NOT EXISTS(
        SELECT 1 FROM medlm.medicine_analyses a
        JOIN medlm.extraction_revisions current_r ON current_r.id=a.current_revision_id
        JOIN medlm.analysis_jobs published_job ON published_job.id=NEW.job_id
        WHERE a.user_id=NEW.user_id AND a.id=NEW.analysis_id
          AND current_r.revision>=NEW.revision AND published_job.state='completed')
        THEN RAISE EXCEPTION 'Incomplete extraction publication'; END IF;
      RETURN NULL;
    END $$;
    CREATE CONSTRAINT TRIGGER extraction_publication_atomic
      AFTER INSERT ON medlm.extraction_revisions DEFERRABLE INITIALLY DEFERRED
      FOR EACH ROW EXECUTE FUNCTION medlm.check_extraction_publication();
    CREATE FUNCTION medlm.check_confirmation_coverage() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF EXISTS(SELECT 1 FROM medlm.analysis_prescription_confirmations WHERE id=NEW.id)
        AND EXISTS(SELECT 1 FROM medlm.analysis_prescription_lines pl
          WHERE pl.user_id=NEW.user_id AND pl.prescription_revision_id=NEW.prescription_revision_id
          AND NOT EXISTS(SELECT 1 FROM medlm.analysis_prescription_confirmation_lines cl
            WHERE cl.user_id=NEW.user_id AND cl.confirmation_id=NEW.id AND cl.line_id=pl.id))
        THEN RAISE EXCEPTION 'Confirmation requires every line disposition'; END IF;
      RETURN NULL;
    END $$;
    CREATE CONSTRAINT TRIGGER confirmation_coverage_atomic
      AFTER INSERT ON medlm.analysis_prescription_confirmations DEFERRABLE INITIALLY DEFERRED
      FOR EACH ROW EXECUTE FUNCTION medlm.check_confirmation_coverage();
    """)
    for table in TABLES:
        op.execute(f"""
        ALTER TABLE medlm.{table} ENABLE ROW LEVEL SECURITY;
        ALTER TABLE medlm.{table} FORCE ROW LEVEL SECURITY;
        CREATE POLICY owner_access ON medlm.{table}
          USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)
          WITH CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
        CREATE INDEX ON medlm.{table}(user_id,analysis_id);
        REVOKE ALL ON medlm.{table} FROM PUBLIC;
        CREATE TRIGGER analysis_child_guard BEFORE INSERT {"OR UPDATE" if table == "analysis_jobs" else ""}
          ON medlm.{table} FOR EACH ROW EXECUTE FUNCTION medlm.guard_analysis_child();
        """)
        if table != "analysis_jobs":
            op.execute(f"""CREATE TRIGGER immutable_history BEFORE UPDATE ON medlm.{table}
              FOR EACH ROW EXECUTE FUNCTION medlm.reject_analysis_history_update()""")
    for function in (
        "guard_analysis_parent",
        "guard_analysis_child",
        "reject_analysis_history_update",
        "check_extraction_publication",
        "check_confirmation_coverage",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION medlm.{function}() FROM PUBLIC")


def downgrade():
    # Migration-owner visibility for the refusal check; transactional rollback restores FORCE RLS.
    for table in ("medicine_analyses", *TABLES):
        op.execute(f"ALTER TABLE medlm.{table} NO FORCE ROW LEVEL SECURITY")
    predicate = " OR ".join(f"EXISTS(SELECT 1 FROM medlm.{t})" for t in TABLES)
    op.execute(f"""DO $$ BEGIN IF {predicate} OR EXISTS(
      SELECT 1 FROM medlm.medicine_analyses WHERE analysis_mode IS NOT NULL
      OR current_job_id IS NOT NULL OR current_revision_id IS NOT NULL OR cancelled_at IS NOT NULL)
      THEN RAISE EXCEPTION 'Analysis data exists; export/erasure required before rollback';
      END IF; END $$;
      ALTER TABLE medlm.medicine_analyses FORCE ROW LEVEL SECURITY;
      DROP TRIGGER stable_analysis_guard ON medlm.medicine_analyses;
      ALTER TABLE medlm.medicine_analyses DROP COLUMN analysis_mode, DROP COLUMN current_job_id,
        DROP COLUMN current_revision_id, DROP COLUMN cancelled_at;
    """)
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE medlm.{table}")
    op.execute("""
      ALTER TABLE medlm.prescriptions DROP CONSTRAINT prescription_analysis_owner;
      DROP FUNCTION medlm.guard_analysis_parent();
      DROP FUNCTION medlm.guard_analysis_child();
      DROP FUNCTION medlm.reject_analysis_history_update();
      DROP FUNCTION medlm.check_extraction_publication();
      DROP FUNCTION medlm.check_confirmation_coverage();
    """)

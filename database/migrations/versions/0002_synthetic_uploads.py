"""Private upload/deletion metadata only; no storage, workers, routes or runtime grants."""

from alembic import op

revision = "0002_synthetic_uploads"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None

OWNED = (
    "uploads",
    "upload_objects",
    "upload_deletion_jobs",
    "upload_audit_events",
    "upload_deletion_receipts",
)


def upgrade():
    op.execute("""
    CREATE TABLE medlm.uploads (
      id uuid PRIMARY KEY,
      user_id uuid NOT NULL REFERENCES medlm.users(id) ON DELETE CASCADE,
      purpose text NOT NULL DEFAULT 'synthetic_validation' CHECK(purpose='synthetic_validation'),
      notice_version text NOT NULL CHECK(notice_version ~ '^[a-zA-Z0-9_.-]{1,64}$'),
      acknowledged_at timestamptz NOT NULL DEFAULT now(),
      document_kind text NOT NULL CHECK(document_kind IN ('strip','bottle','tube','box','prescription')),
      mime text NOT NULL CHECK(mime IN ('image/jpeg','image/png','image/webp')),
      declared_bytes bigint NOT NULL CHECK(declared_bytes BETWEEN 1 AND 10485760),
      ticket_hash text NOT NULL UNIQUE CHECK(ticket_hash ~ '^[0-9a-f]{64}$'),
      ticket_expires_at timestamptz NOT NULL,
      consumed_at timestamptz,
      retain_for_review boolean NOT NULL DEFAULT false,
      expires_at timestamptz NOT NULL,
      status text NOT NULL DEFAULT 'initiated'
        CHECK(status IN ('initiated','accepted','rejected','deleting','deleted')),
      accepted_at timestamptz,
      deletion_requested_at timestamptz,
      purged_at timestamptz,
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(),
      version bigint NOT NULL DEFAULT 1 CHECK(version > 0),
      UNIQUE(user_id,id),
      CHECK(expires_at > created_at AND expires_at <= created_at + interval '24 hours'),
      CHECK(ticket_expires_at > created_at AND ticket_expires_at <= created_at + interval '5 minutes'
        AND ticket_expires_at <= expires_at),
      CHECK(consumed_at IS NULL OR consumed_at BETWEEN created_at AND ticket_expires_at),
      CHECK(accepted_at IS NULL OR (consumed_at IS NOT NULL
        AND accepted_at >= consumed_at AND accepted_at <= expires_at)),
      CHECK(status <> 'accepted' OR accepted_at IS NOT NULL),
      CHECK((status IN ('deleting','deleted')) = (deletion_requested_at IS NOT NULL)),
      CHECK((status='deleted') = (purged_at IS NOT NULL)),
      CHECK(purged_at IS NULL OR purged_at >= deletion_requested_at)
    );
    CREATE TABLE medlm.upload_objects (
      id uuid PRIMARY KEY, user_id uuid NOT NULL, upload_id uuid NOT NULL,
      object_key uuid NOT NULL UNIQUE,
      kind text NOT NULL CHECK(kind IN ('original','sanitized','review','temporary')),
      checksum_sha256 text CHECK(checksum_sha256 ~ '^[0-9a-f]{64}$'),
      byte_size bigint CHECK(byte_size BETWEEN 1 AND 10485760),
      created_at timestamptz NOT NULL DEFAULT now(),
      expires_at timestamptz NOT NULL,
      purged_at timestamptz,
      UNIQUE(user_id,id), UNIQUE(user_id,upload_id,id),
      FOREIGN KEY(user_id,upload_id) REFERENCES medlm.uploads(user_id,id) ON DELETE CASCADE,
      CHECK(expires_at > created_at),
      CHECK((checksum_sha256 IS NULL) = (byte_size IS NULL)),
      CHECK(purged_at IS NULL OR purged_at >= created_at)
    );
    CREATE TABLE medlm.upload_deletion_jobs (
      id uuid PRIMARY KEY, user_id uuid NOT NULL, upload_id uuid NOT NULL,
      object_id uuid NOT NULL UNIQUE,
      reason text NOT NULL CHECK(reason IN ('expiry','cancelled','rejected','completed','reconciliation')),
      state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','leased','retry','completed')),
      available_at timestamptz NOT NULL DEFAULT now(),
      lease_until timestamptz, lease_token uuid,
      fencing_token bigint NOT NULL DEFAULT 0 CHECK(fencing_token >= 0),
      attempts int NOT NULL DEFAULT 0 CHECK(attempts >= 0),
      last_error_code text CHECK(last_error_code IN ('storage_unavailable','timeout','verification_failed')),
      created_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz,
      UNIQUE(user_id,id),
      FOREIGN KEY(user_id,upload_id,object_id)
        REFERENCES medlm.upload_objects(user_id,upload_id,id) ON DELETE CASCADE,
      CHECK((state='leased') = (lease_until IS NOT NULL AND lease_token IS NOT NULL)),
      CHECK(state='leased' OR (lease_until IS NULL AND lease_token IS NULL)),
      CHECK(lease_until IS NULL OR lease_until > available_at),
      CHECK(state <> 'leased' OR (fencing_token > 0 AND attempts > 0)),
      CHECK((state='completed') = (completed_at IS NOT NULL))
    );
    CREATE TABLE medlm.upload_audit_events (
      id uuid PRIMARY KEY, user_id uuid NOT NULL, upload_id uuid NOT NULL,
      event text NOT NULL CHECK(event IN
        ('initiated','accepted','rejected','deletion_requested','purge_verified','purge_failed')),
      recorded_at timestamptz NOT NULL DEFAULT now(),
      expires_at timestamptz NOT NULL,
      UNIQUE(user_id,id),
      FOREIGN KEY(user_id,upload_id) REFERENCES medlm.uploads(user_id,id) ON DELETE CASCADE,
      CHECK(expires_at > recorded_at AND expires_at <= recorded_at + interval '90 days')
    );
    CREATE TABLE medlm.upload_deletion_receipts (
      id uuid PRIMARY KEY,
      user_id uuid REFERENCES medlm.users(id) ON DELETE SET NULL,
      object_key uuid NOT NULL UNIQUE,
      verified_at timestamptz NOT NULL,
      expires_at timestamptz NOT NULL,
      UNIQUE(user_id,id),
      CHECK(expires_at > verified_at AND expires_at <= verified_at + interval '90 days')
    );
    COMMENT ON TABLE medlm.upload_deletion_receipts IS
      'Opaque restore/re-erasure ledger. No image hash, filename or clinical payload. '
      'Receipt is a worker assertion; database cannot verify physical deletion.';
    CREATE TABLE medlm.upload_safeguard_runs (
      id uuid PRIMARY KEY,
      kind text NOT NULL CHECK(kind IN ('deletion_worker','independent_sweep','reconciliation')),
      started_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz,
      outcome text NOT NULL DEFAULT 'running' CHECK(outcome IN ('running','ok','failed')),
      overdue_objects int NOT NULL DEFAULT 0 CHECK(overdue_objects >= 0),
      expires_at timestamptz NOT NULL,
      CHECK((outcome='running') = (finished_at IS NULL)),
      CHECK(finished_at IS NULL OR finished_at >= started_at),
      CHECK(expires_at > started_at AND expires_at <= started_at + interval '30 days')
    );
    CREATE INDEX upload_expiry ON medlm.uploads(expires_at) WHERE status <> 'deleted';
    CREATE INDEX object_expiry ON medlm.upload_objects(expires_at) WHERE purged_at IS NULL;
    CREATE INDEX object_upload ON medlm.upload_objects(user_id,upload_id);
    CREATE UNIQUE INDEX one_upload_copy ON medlm.upload_objects(upload_id,kind)
      WHERE kind <> 'temporary';
    CREATE INDEX deletion_ready ON medlm.upload_deletion_jobs(available_at) WHERE state IN ('pending','retry');
    CREATE INDEX deletion_lease ON medlm.upload_deletion_jobs(lease_until) WHERE state='leased';
    CREATE INDEX deletion_upload ON medlm.upload_deletion_jobs(user_id,upload_id);
    CREATE INDEX audit_upload ON medlm.upload_audit_events(user_id,upload_id,recorded_at);
    CREATE INDEX audit_expiry ON medlm.upload_audit_events(expires_at);
    CREATE INDEX receipt_expiry ON medlm.upload_deletion_receipts(expires_at);
    CREATE INDEX safeguard_expiry ON medlm.upload_safeguard_runs(expires_at);
    CREATE INDEX safeguard_latest ON medlm.upload_safeguard_runs(kind,started_at DESC);
    """)
    for table in (*OWNED, "upload_safeguard_runs"):
        op.execute(f"ALTER TABLE medlm.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE medlm.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON medlm.{table} FROM PUBLIC")
        if table in OWNED:
            op.execute(f"""CREATE POLICY owner_access ON medlm.{table}
              USING(user_id = NULLIF(current_setting('app.user_id',true),'')::uuid)
              WITH CHECK(user_id = NULLIF(current_setting('app.user_id',true),'')::uuid)""")
    # SECURITY INVOKER, qualified relations, no runtime grants. Cross-user maintenance
    # policies/claim functions will be introduced only with the separately reviewed worker.
    op.execute("""
    CREATE FUNCTION medlm.guard_upload() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP='INSERT' THEN
        IF NEW.status <> 'initiated' OR NEW.consumed_at IS NOT NULL OR NEW.accepted_at IS NOT NULL
          OR NEW.purged_at IS NOT NULL OR NEW.deletion_requested_at IS NOT NULL THEN
          RAISE EXCEPTION 'upload must start initiated' USING ERRCODE='23514'; END IF;
        RETURN NEW;
      END IF;
      IF TG_OP='DELETE' THEN
        IF EXISTS(SELECT 1 FROM medlm.upload_objects WHERE upload_id=OLD.id AND purged_at IS NULL)
        THEN RAISE EXCEPTION 'unpurged object inventory' USING ERRCODE='23514'; END IF;
        RETURN OLD;
      END IF;
      IF (to_jsonb(NEW) - ARRAY['status','accepted_at','consumed_at','deletion_requested_at',
          'purged_at','expires_at','updated_at','version']) IS DISTINCT FROM
         (to_jsonb(OLD) - ARRAY['status','accepted_at','consumed_at','deletion_requested_at',
          'purged_at','expires_at','updated_at','version'])
        OR NEW.expires_at > OLD.expires_at
        OR (OLD.consumed_at IS NOT NULL AND NEW.consumed_at IS DISTINCT FROM OLD.consumed_at)
        OR (OLD.accepted_at IS NOT NULL AND NEW.accepted_at IS DISTINCT FROM OLD.accepted_at)
        OR (OLD.deletion_requested_at IS NOT NULL AND
            NEW.deletion_requested_at IS DISTINCT FROM OLD.deletion_requested_at)
        OR (OLD.purged_at IS NOT NULL AND NEW.purged_at IS DISTINCT FROM OLD.purged_at)
      THEN RAISE EXCEPTION 'immutable upload metadata' USING ERRCODE='23514'; END IF;
      IF NEW.status <> OLD.status AND NOT (
        (OLD.status='initiated' AND NEW.status IN ('accepted','rejected','deleting')) OR
        (OLD.status IN ('accepted','rejected') AND NEW.status='deleting') OR
        (OLD.status='deleting' AND NEW.status='deleted'))
      THEN RAISE EXCEPTION 'invalid upload transition' USING ERRCODE='23514'; END IF;
      IF NEW.status='deleted' AND EXISTS(
        SELECT 1 FROM medlm.upload_objects WHERE upload_id=OLD.id AND purged_at IS NULL)
      THEN RAISE EXCEPTION 'unpurged object inventory' USING ERRCODE='23514'; END IF;
      NEW.version := OLD.version + 1; NEW.updated_at := clock_timestamp();
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_upload BEFORE INSERT OR UPDATE OR DELETE ON medlm.uploads
      FOR EACH ROW EXECUTE FUNCTION medlm.guard_upload();

    CREATE FUNCTION medlm.guard_upload_object() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE parent medlm.uploads%ROWTYPE;
    BEGIN
      IF TG_OP='DELETE' THEN
        IF OLD.purged_at IS NULL THEN
          RAISE EXCEPTION 'unpurged object inventory' USING ERRCODE='23514'; END IF;
        RETURN OLD;
      END IF;
      IF TG_OP='UPDATE' THEN
        IF (to_jsonb(NEW) - ARRAY['checksum_sha256','byte_size','purged_at']) IS DISTINCT FROM
           (to_jsonb(OLD) - ARRAY['checksum_sha256','byte_size','purged_at'])
          OR (OLD.checksum_sha256 IS NOT NULL AND
            (NEW.checksum_sha256 IS DISTINCT FROM OLD.checksum_sha256 OR
             NEW.byte_size IS DISTINCT FROM OLD.byte_size))
          OR (OLD.purged_at IS NOT NULL AND NEW.purged_at IS DISTINCT FROM OLD.purged_at)
        THEN RAISE EXCEPTION 'immutable object metadata' USING ERRCODE='23514'; END IF;
      END IF;
      SELECT * INTO parent FROM medlm.uploads
        WHERE id=NEW.upload_id AND user_id=NEW.user_id FOR UPDATE;
      IF NOT FOUND THEN RAISE EXCEPTION 'unavailable upload' USING ERRCODE='23514'; END IF;
      IF TG_OP='INSERT' OR (TG_OP='UPDATE' AND OLD.checksum_sha256 IS NULL
                            AND NEW.checksum_sha256 IS NOT NULL) THEN
        IF parent.status IN ('rejected','deleting','deleted') OR parent.expires_at <= clock_timestamp()
          OR NEW.expires_at > parent.expires_at
          OR (NEW.kind='review' AND NOT parent.retain_for_review)
        THEN RAISE EXCEPTION 'upload unavailable for object write' USING ERRCODE='23514'; END IF;
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_upload_object BEFORE INSERT OR UPDATE OR DELETE ON medlm.upload_objects
      FOR EACH ROW EXECUTE FUNCTION medlm.guard_upload_object();

    CREATE FUNCTION medlm.guard_upload_job() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF (to_jsonb(NEW) - ARRAY['state','available_at','lease_until','lease_token','fencing_token',
          'attempts','last_error_code','completed_at']) IS DISTINCT FROM
         (to_jsonb(OLD) - ARRAY['state','available_at','lease_until','lease_token','fencing_token',
          'attempts','last_error_code','completed_at']) OR NEW.attempts < OLD.attempts
        OR NEW.fencing_token < OLD.fencing_token OR OLD.state='completed'
      THEN RAISE EXCEPTION 'invalid deletion job update' USING ERRCODE='23514'; END IF;
      IF NEW.state='leased' AND NEW.lease_token IS DISTINCT FROM OLD.lease_token
        AND (NEW.fencing_token <= OLD.fencing_token OR NEW.attempts <= OLD.attempts)
      THEN RAISE EXCEPTION 'lease requires new fence and attempt' USING ERRCODE='23514'; END IF;
      IF NEW.state='completed' AND NOT EXISTS(
        SELECT 1 FROM medlm.upload_objects WHERE id=NEW.object_id AND user_id=NEW.user_id
          AND purged_at IS NOT NULL) THEN
        RAISE EXCEPTION 'object purge not recorded' USING ERRCODE='23514'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_upload_job BEFORE UPDATE ON medlm.upload_deletion_jobs
      FOR EACH ROW EXECUTE FUNCTION medlm.guard_upload_job();

    CREATE FUNCTION medlm.guard_upload_audit() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      RAISE EXCEPTION 'audit events are immutable' USING ERRCODE='23514';
    END $$;
    CREATE TRIGGER guard_upload_audit BEFORE UPDATE ON medlm.upload_audit_events
      FOR EACH ROW EXECUTE FUNCTION medlm.guard_upload_audit();
    CREATE FUNCTION medlm.guard_upload_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP='DELETE' THEN
        IF OLD.expires_at > clock_timestamp() THEN
          RAISE EXCEPTION 'retain unexpired deletion receipt' USING ERRCODE='23514'; END IF;
        RETURN OLD;
      END IF;
      IF (to_jsonb(NEW) - 'user_id') IS DISTINCT FROM (to_jsonb(OLD) - 'user_id')
        OR (NEW.user_id IS DISTINCT FROM OLD.user_id AND NEW.user_id IS NOT NULL) THEN
        RAISE EXCEPTION 'receipt is immutable except erasure unlink' USING ERRCODE='23514'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_upload_receipt BEFORE UPDATE OR DELETE ON medlm.upload_deletion_receipts
      FOR EACH ROW EXECUTE FUNCTION medlm.guard_upload_receipt();
    REVOKE ALL ON FUNCTION medlm.guard_upload(), medlm.guard_upload_object(),
      medlm.guard_upload_job(), medlm.guard_upload_audit(), medlm.guard_upload_receipt() FROM PUBLIC;
    """)


def downgrade():
    # Deliberately refuse to discard deletion inventory while objects may remain.
    # Owner must see every row; changes roll back if a guard rejects downgrade.
    op.execute("ALTER TABLE medlm.upload_objects NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE medlm.upload_deletion_receipts NO FORCE ROW LEVEL SECURITY")
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM medlm.upload_objects WHERE purged_at IS NULL) THEN
        RAISE EXCEPTION 'purge objects before downgrade' USING ERRCODE='23514';
      END IF;
      IF EXISTS(SELECT 1 FROM medlm.upload_deletion_receipts WHERE expires_at > now()) THEN
        RAISE EXCEPTION 'retain unexpired deletion receipts' USING ERRCODE='23514';
      END IF;
    END $$""")
    for table in (
        "upload_safeguard_runs",
        "upload_deletion_receipts",
        "upload_audit_events",
        "upload_deletion_jobs",
        "upload_objects",
        "uploads",
    ):
        op.execute(f"DROP TABLE medlm.{table}")
    for function in (
        "guard_upload",
        "guard_upload_object",
        "guard_upload_job",
        "guard_upload_audit",
        "guard_upload_receipt",
    ):
        op.execute(f"DROP FUNCTION medlm.{function}()")

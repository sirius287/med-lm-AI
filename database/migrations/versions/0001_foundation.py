"""Owned foundation tables; no clinical records or active scheduling endpoints."""

from alembic import op

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None

OWNED = [
    "profiles",
    "medicine_analyses",
    "prescriptions",
    "prescription_medicines",
    "prescription_confirmations",
    "medications",
    "medication_schedules",
    "dose_occurrences",
    "dose_events",
]


def upgrade():
    op.execute("CREATE SCHEMA medlm")
    op.execute("CREATE SCHEMA medlm_auth")
    op.execute("REVOKE ALL ON SCHEMA medlm, medlm_auth FROM PUBLIC")
    op.execute("""
        CREATE TABLE medlm.users (
          id uuid PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now(),
          disabled_at timestamptz
        );
        COMMENT ON TABLE medlm.users IS
          'Supabase subject projection only; no passwords. Auth remains provider-owned.';
        CREATE TABLE medlm.profiles (
          user_id uuid PRIMARY KEY REFERENCES medlm.users(id) ON DELETE CASCADE,
          locale text NOT NULL DEFAULT 'en-IN', country char(2) NOT NULL DEFAULT 'IN',
          time_zone text NOT NULL DEFAULT 'Asia/Kolkata', version int NOT NULL DEFAULT 1,
          CHECK (locale IN ('en-IN','hi-IN','te-IN'))
        );
        CREATE TABLE medlm.medicine_analyses (
          id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES medlm.users(id) ON DELETE CASCADE,
          kind text NOT NULL CHECK(kind IN ('medicine','prescription')),
          country char(2) NOT NULL, locale text NOT NULL,
          state text NOT NULL DEFAULT 'queued' CHECK(state IN
            ('queued','validating','extracting','retrieving','validating_output',
             'completed','needs_input','failed','cancelled')),
          created_at timestamptz NOT NULL DEFAULT now(), version int NOT NULL DEFAULT 1,
          UNIQUE(user_id,id)
        );
        CREATE TABLE medlm.prescriptions (
          id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES medlm.users(id) ON DELETE CASCADE,
          analysis_id uuid, revision int NOT NULL DEFAULT 1 CHECK(revision > 0),
          status text NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','reviewed','deleted')),
          created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(user_id,id),
          FOREIGN KEY(user_id,analysis_id) REFERENCES medlm.medicine_analyses(user_id,id)
        );
        CREATE TABLE medlm.prescription_medicines (
          id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES medlm.users(id) ON DELETE CASCADE,
          prescription_id uuid NOT NULL, ordinal int NOT NULL CHECK(ordinal >= 0),
          fields jsonb NOT NULL, revision int NOT NULL CHECK(revision > 0),
          UNIQUE(user_id,id), UNIQUE(prescription_id,revision,ordinal),
          FOREIGN KEY(user_id,prescription_id) REFERENCES medlm.prescriptions(user_id,id)
            ON DELETE CASCADE
        );
        CREATE TABLE medlm.prescription_confirmations (
          id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES medlm.users(id) ON DELETE CASCADE,
          prescription_id uuid NOT NULL, revision int NOT NULL CHECK(revision > 0),
          reviewed_fields jsonb NOT NULL, confirmed_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE(user_id,id),
          FOREIGN KEY(user_id,prescription_id) REFERENCES medlm.prescriptions(user_id,id)
            ON DELETE CASCADE
        );
        CREATE TABLE medlm.medications (
          id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES medlm.users(id) ON DELETE CASCADE,
          display_name text NOT NULL, strength_text text, dose_text text NOT NULL,
          origin text NOT NULL CHECK(origin IN ('manual','confirmed_prescription')),
          instruction_snapshot jsonb NOT NULL, reviewed_at timestamptz NOT NULL,
          version int NOT NULL DEFAULT 1, deleted_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(user_id,id)
        );
        CREATE TABLE medlm.medication_schedules (
          id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES medlm.users(id) ON DELETE CASCADE,
          medication_id uuid NOT NULL, revision int NOT NULL CHECK(revision > 0),
          kind text NOT NULL CHECK(kind IN ('daily_times','weekdays','fixed_interval','one_time')),
          schedule jsonb NOT NULL, time_zone text NOT NULL, start_date date NOT NULL,
          end_date date, retired_at timestamptz,
          UNIQUE(user_id,id), UNIQUE(medication_id,revision),
          CHECK(end_date IS NULL OR end_date >= start_date),
          FOREIGN KEY(user_id,medication_id) REFERENCES medlm.medications(user_id,id)
            ON DELETE CASCADE
        );
        CREATE UNIQUE INDEX one_active_schedule ON medlm.medication_schedules(medication_id)
          WHERE retired_at IS NULL;
        CREATE TABLE medlm.dose_occurrences (
          id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES medlm.users(id) ON DELETE CASCADE,
          schedule_id uuid NOT NULL, occurrence_key text NOT NULL, planned_at timestamptz NOT NULL,
          dose_snapshot jsonb NOT NULL, version int NOT NULL DEFAULT 1,
          status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','taken','skipped','cancelled')),
          UNIQUE(user_id,id), UNIQUE(schedule_id,occurrence_key),
          FOREIGN KEY(user_id,schedule_id) REFERENCES medlm.medication_schedules(user_id,id)
            ON DELETE CASCADE
        );
        CREATE TABLE medlm.dose_events (
          id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES medlm.users(id) ON DELETE CASCADE,
          occurrence_id uuid NOT NULL, kind text NOT NULL
            CHECK(kind IN ('taken','skipped','snoozed','corrected')),
          client_at timestamptz NOT NULL, recorded_at timestamptz NOT NULL DEFAULT now(),
          payload jsonb NOT NULL, UNIQUE(user_id,id),
          FOREIGN KEY(user_id,occurrence_id) REFERENCES medlm.dose_occurrences(user_id,id)
            ON DELETE CASCADE
        );
        CREATE TABLE medlm.verification_sources (
          id uuid PRIMARY KEY, provider text NOT NULL, external_id text NOT NULL,
          revision text NOT NULL, country char(2) NOT NULL, locale text NOT NULL,
          url text NOT NULL, content_hash text NOT NULL, retrieved_at timestamptz NOT NULL,
          verified_at timestamptz, license_policy jsonb NOT NULL,
          UNIQUE(provider,external_id,revision,content_hash)
        );
        CREATE TABLE medlm_auth.web_sessions (
          id_hash text PRIMARY KEY, user_id uuid NOT NULL REFERENCES medlm.users(id) ON DELETE CASCADE,
          encrypted_tokens text NOT NULL, csrf_token text NOT NULL,
          expires_at timestamptz NOT NULL, revoked_at timestamptz
        );
        CREATE TABLE medlm_auth.revoked_sessions (
          session_id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES medlm.users(id) ON DELETE CASCADE,
          expires_at timestamptz NOT NULL
        );
    """)
    for table in ["users", *OWNED]:
        column = "id" if table == "users" else "user_id"
        op.execute(f"ALTER TABLE medlm.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE medlm.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY owner_access ON medlm.{table}
          USING ({column} = NULLIF(current_setting('app.user_id', true), '')::uuid)
          WITH CHECK ({column} = NULLIF(current_setting('app.user_id', true), '')::uuid)""")
        if table not in ("users", "profiles"):
            op.execute(f"CREATE INDEX ON medlm.{table}(user_id)")
    op.execute("CREATE INDEX ON medlm.dose_occurrences(user_id,planned_at)")
    op.execute("CREATE INDEX ON medlm.dose_events(user_id,recorded_at DESC)")
    op.execute("CREATE INDEX ON medlm_auth.web_sessions(expires_at)")
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA medlm, medlm_auth FROM PUBLIC")


def downgrade():
    # Only this migration's schemas; never touches Supabase auth/storage schemas.
    op.execute("DROP SCHEMA medlm_auth CASCADE")
    op.execute("DROP SCHEMA medlm CASCADE")

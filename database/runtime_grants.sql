-- Run as migration owner after creating medlm_runtime with a unique local password.
-- Runtime must be NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS.
GRANT USAGE ON SCHEMA medlm, medlm_auth TO medlm_runtime;
GRANT SELECT, INSERT, UPDATE ON medlm.users, medlm.profiles TO medlm_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON medlm_auth.web_sessions, medlm_auth.revoked_sessions TO medlm_runtime;
-- Applied after migration 0003; explicit grants cannot expose future auth tables.
GRANT SELECT, INSERT, UPDATE, DELETE ON medlm_auth.auth_throttles TO medlm_runtime;
-- Phase 3A manual management only. No grants on prescription/analysis/reference tables.
GRANT SELECT, INSERT, UPDATE, DELETE ON medlm.medications, medlm.medication_schedules,
  medlm.dose_occurrences TO medlm_runtime;
GRANT SELECT, INSERT, DELETE ON medlm.medication_instruction_revisions,
  medlm.dose_events TO medlm_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON medlm.idempotency_records TO medlm_runtime;

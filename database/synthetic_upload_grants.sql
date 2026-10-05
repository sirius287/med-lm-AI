-- OPTIONAL: disposable synthetic harness database only, after migration 0004.
-- Provision medlm_upload_worker separately as NOSUPERUSER NOCREATEDB NOCREATEROLE
-- NOBYPASSRLS; NEVER grant membership to medlm_runtime. No provider credentials.
GRANT SELECT, INSERT ON medlm.uploads, medlm.upload_objects,
  medlm.upload_deletion_jobs TO medlm_runtime;
GRANT UPDATE (status, consumed_at, accepted_at, deletion_requested_at) ON medlm.uploads TO medlm_runtime;
GRANT UPDATE (checksum_sha256, byte_size) ON medlm.upload_objects TO medlm_runtime;
GRANT SELECT, INSERT ON medlm.upload_audit_events TO medlm_runtime;
GRANT SELECT ON medlm.upload_deletion_receipts, medlm.upload_safeguard_runs TO medlm_runtime;
GRANT USAGE ON SCHEMA medlm TO medlm_upload_worker;
GRANT SELECT, UPDATE, DELETE ON medlm.uploads, medlm.upload_objects TO medlm_upload_worker;
GRANT SELECT, INSERT, DELETE ON medlm.upload_audit_events,
  medlm.upload_deletion_receipts TO medlm_upload_worker;
GRANT SELECT, INSERT, UPDATE, DELETE ON medlm.upload_deletion_jobs,
  medlm.upload_safeguard_runs TO medlm_upload_worker;

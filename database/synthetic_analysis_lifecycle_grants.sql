-- Optional synthetic harness only, after migration 0007 and the existing
-- runtime, synthetic-upload and synthetic-analysis grant scripts.
-- No new tables, worker roles, memberships or cross-owner policies.
GRANT UPDATE(expired_at) ON medlm.medicine_analyses TO medlm_runtime;
GRANT UPDATE(lease_token,lease_until,fencing_token,lifecycle_version)
  ON medlm.analysis_jobs TO medlm_runtime;

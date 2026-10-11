-- Explicit synthetic harness only, after prior synthetic grants and migration 0008.
DO $$ BEGIN
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='medlm_runtime'
    AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls))
    THEN RAISE EXCEPTION 'Unsafe runtime role attributes'; END IF;
END $$;
GRANT UPDATE(safe_error_code) ON medlm.analysis_jobs TO medlm_runtime;

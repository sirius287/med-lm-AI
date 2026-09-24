-- Disposable test cluster only. No login credentials, no medical records.
DO $body$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'medlm_runtime') THEN
    CREATE ROLE medlm_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
  END IF;
END
$body$;

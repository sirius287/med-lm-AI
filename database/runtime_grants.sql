-- Run as migration owner after creating medlm_runtime with a unique local password.
-- Runtime must be NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS.
GRANT USAGE ON SCHEMA medlm, medlm_auth TO medlm_runtime;
GRANT SELECT, INSERT, UPDATE ON medlm.users, medlm.profiles TO medlm_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA medlm_auth TO medlm_runtime;
-- Clinical tables intentionally have no runtime grants in Phase 1.
-- Later clinical services must add reviewed grants and enforce confirmation workflows.

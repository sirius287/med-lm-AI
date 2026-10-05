-- Provision this separate NOSUPERUSER NOBYPASSRLS role before applying.
GRANT USAGE ON SCHEMA medlm TO medlm_medication_maintenance;
GRANT SELECT, DELETE ON medlm.idempotency_records TO medlm_medication_maintenance;

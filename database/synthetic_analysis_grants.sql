-- Explicit opt-in for the local synthetic persistence harness only.
-- Apply as migration owner; do not append this to normal runtime provisioning.
-- No worker/maintenance role or cross-owner policy is introduced.
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='medlm_runtime'
    AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls)) THEN
    RAISE EXCEPTION 'Unsafe runtime role attributes';
  END IF;
END $$;
GRANT USAGE ON SCHEMA medlm TO medlm_runtime;
GRANT SELECT, INSERT, DELETE ON medlm.medicine_analyses, medlm.prescriptions TO medlm_runtime;
GRANT UPDATE(current_job_id,current_revision_id,cancelled_at,version)
  ON medlm.medicine_analyses TO medlm_runtime;
GRANT SELECT ON medlm.uploads TO medlm_runtime;
-- FOR UPDATE admission lock requires an UPDATE privilege; no new ability to change
-- upload lifecycle is needed: existing synthetic_upload_grants.sql supplies it.
GRANT SELECT, INSERT ON
  medlm.analysis_uploads, medlm.analysis_jobs, medlm.extraction_revisions,
  medlm.identity_candidate_sets, medlm.identity_candidates, medlm.analysis_reviews,
  medlm.analysis_prescription_drafts, medlm.analysis_prescription_revisions,
  medlm.analysis_prescription_lines, medlm.analysis_prescription_confirmations,
  medlm.analysis_prescription_confirmation_lines TO medlm_runtime;
GRANT UPDATE(state) ON medlm.analysis_jobs TO medlm_runtime;

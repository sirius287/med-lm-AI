# Phase 3B Chunk 6 engineering audit

Date: 2026-10-15. Base/HEAD: cdadf34 on main. No staging, commit or push authorized.
This is a source-level engineering audit with local synthetic regression validation,
not a penetration test, live-service certification or clinical validation.

## Checkpoint and preservation

The initial index was empty. Nine modified tracked files and three untracked report
files matched the reviewed Chunk 6 checkpoint. The two requested defensive fixes and
their tests were already present; they were inspected and verified, not rewritten.
Existing Git history, migrations 0001-0009, grants, frontend and dependencies were preserved.

Verified committed sequence: edbadbc (Chunk 1), abea49f (Chunk 2), 4775ed1 (Chunk 3),
97fa471 (Chunk 4), 4ac50ca (Chunk 5), then documentation correction cdadf34.
Chunk 6 remains uncommitted and awaiting review. Chunk 7 has not started.

## Findings and disposition

| ID / classification | Severity and practical impact | Exact location / evidence | Minimal remedy and regression | Dependencies / risk |
| --- | --- | --- | --- | --- |
| F1 Confirmed defect, previously corrected | Medium: malformed persisted observations escaped the intended safe report response | services/api/medlm_api/analysis_report.py, SyntheticReports.get; test_malformed_persisted_observations_return_safe_conflict in services/api/tests/test_analysis_report.py | Existing scoped ValidationError handling produces 409 report_unavailable; test_target_errors_are_not_reclassified preserves authorization/database/programming errors | No schema or authorization change; verified existing fix |
| F2 Data-integrity risk, previously corrected | Medium: inconsistent conflict metadata could misrepresent uncertainty in a constructed report | packages/backend_domain/medlm_domain/report.py, AnalysisReport.boundaries and _observation_conflicts | Existing validation requires matching conflict state, complete evidence references and exact original ambiguity summaries; test_conflict_state_requires_complete_consistent_evidence and test_observation_conflict_summaries_match_original | Synthetic evidence remains non-authoritative; medical values remain null; verified existing fix |
| F3 Confirmed security defect, corrected in this audit | Medium: a medication request authenticated earlier could write after principal expiry while waiting on locks | services/api/medlm_api/medication_routes.py, context; new test_session_expiring_after_authentication_cannot_write in services/api/tests/test_manual_medication_api.py initially received 201 instead of 401 | Recheck principal.expires_at against utcnow after existing locks/revocation check and before yielding service; regression requires 401 and zero medication writes | Reuses existing upload/report rule; no new policy, grant or schema; normal fresh sessions covered by existing API tests |
| F4 Confirmed privacy/data-integrity defect, corrected in this audit | Medium in the synthetic harness; explicit text erasure left cached encrypted extraction/review responses until normal replay expiry | services/api/medlm_api/analysis_repository.py, AnalysisRepository.erase; test_analysis_erasure_clears_owned_replay_bodies_only initially found response bodies retained after erasure | Clear encrypted_response and set invalidated=true for exact user/resource in the erasure transaction, after version validation; preserve original expiry and unrelated resource responses | Reuses existing medication erasure/idempotency mechanism and grants; no upload/deletion workflow change |
| F5 Missing regression coverage, added | Medium: documented saved-text access/erasure guarantees lacked report-level tests for several lifecycle cases | services/api/tests/test_analysis_report.py | Added test_final_transcription_remains_unverified_after_image_expiry, test_saved_report_survives_verified_upload_metadata_removal and test_report_snapshot_serializes_with_analysis_erasure | Real disposable PostgreSQL and restricted runtime/maintenance roles; no changed access policy |
| F6 Maintainability limitation, deferred | Low: no checked-in CI workflow, and the current complete-suite safety wrapper lives in ignored .local | .github is absent; .local/chunk6_validate.py; README.md testing instructions | Keep explicit database-isolation checks for this audit; consider a reviewed committed harness/CI task after this checkpoint | No CI/deployment expansion here. Environment-only tests can skip when database variables are absent; passing with skips is not full database validation |

No optional redesign, stack replacement, package upgrade or speculative refactoring was
implemented. No new issue required a migration, broad grant, external service, change in
product behavior or security-policy redesign.

## Subsystem review

| Subsystem | Source and boundaries inspected | Assessment / limits |
| --- | --- | --- |
| Backend/domain/API | main.py, config.py, errors.py, auth_dependencies.py, medication_routes.py, medication_service.py, domain_idempotency.py, analysis_routes.py; medlm_domain analysis/extraction/review/report/scheduling contracts | Typed domain inputs, versioned routes, safe error/logging boundaries and server-only configuration retained. Synthetic routes require explicit test injection. No report persistence |
| Authentication/session | auth.py AuthService, SupabaseGateway, SessionRepository; auth_rate_limit.py; owned transaction boundaries | Signature/identity/session binding, cookie Origin/CSRF, local revocation/account checks and logout locks retained. F3 closes transaction-boundary expiry gap. Live provider behavior remains unverified |
| Database/privacy | Database.transaction, runtime/synthetic grants, migrations and migration/repository tests; upload_storage.py, uploads.py, upload_maintenance.py | Transaction-local owner context, FORCE RLS, composite FKs, immutable history and restricted roles retained. F4 includes replay text in erasure. Independent deletion jobs, receipts and original deadlines preserved |
| Analysis/extraction/review | analysis_lifecycle.py, analysis_repository.py, synthetic_extraction.py, synthetic_fixtures.py, extraction_adapters.py, analysis_review.py, report.py and analysis_report.py | Stable analysis/current revision, job fencing, dual hashes, review/verification separation, exact review binding and non-authoritative synthetic provenance retained. No provider transport or clinical lookup enabled |
| Flutter architecture/UX | app/app.dart, app/providers.dart, core configuration/API/logging/HTTP adapters, auth service/controller, medication service/controller/providers/history, design theme, locale catalogs and accessibility/recovery tests | Existing shared frontend, owner-scope disposal, credential clearing, both themes and English/Hindi/Telugu scaffolding preserved. No frontend edits or new workflow. No fresh Flutter build/device claim |
| Tooling/release | pyproject.toml, dependency locks, scripts/export_contract.py, scripts/generate_manual_client.py, test fixtures, README, SETUP_WINDOWS and synthetic upload runbook | Existing dependencies retained; generated manual client parity checked. Disposable DB wrapper used before every database run. CI, device, translation and operations gates remain separate |

The 24 required medical-information keys are compared with REQUIREMENTS.md by an actual
contract test. No authoritative source was checked: the API emits unavailable fields with
null values, accurate reasons and empty evidence references. Pure synthetic conflict tests
preserve alternatives with null medical values. Human-reviewed text never verifies medicine.

## Validation

| Command / check | Actual result |
| --- | --- |
| uv run python .local/chunk6_validate.py services/api/tests/test_analysis_report.py (before audit additions) | 50 passed |
| uv run python .local/chunk6_validate.py services/api/tests/test_manual_medication_api.py -k session_expiring_after_authentication | 1 failed before fix: response was 201 instead of 401 |
| uv run python .local/chunk6_validate.py services/api/tests/test_manual_medication_api.py | 8 passed after fix |
| uv run python .local/chunk6_validate.py services/api/tests/test_analysis_report.py -k analysis_erasure_clears | 1 failed before fix; 1 passed after fix |
| uv run python .local/chunk6_validate.py services/api/tests/test_analysis_report.py services/api/tests/test_analysis_schema.py services/api/tests/test_manual_medication_api.py | 82 passed, 0 failed, 0 skipped; 54 deprecation warnings; 64.87 seconds |
| uv run python .local/chunk6_validate.py (complete suite) | 334 passed, 0 failed, 0 skipped; 271 deprecation warnings; 301.43 seconds |
| uv run ruff check services packages database | Passed |
| uv run python scripts/generate_manual_client.py --check | Passed, no generated files changed |
| git diff --check | Passed; Git LF/CRLF notices only |

The complete-suite command was piped through Tee-Object to retain actual output at
`.local/chunk6-audit-full-tests.log`. The ignored harness validates 127.0.0.1:15432,
creates a randomly named empty database and verifies its identity before migrations/tests.
All database tests/migration paths ran on disposable local databases. Shared medlm_test
was read only to compare its data fingerprint and 0005 baseline before/after each run;
both remained unchanged. All disposable databases were removed, runtime role flags were
checked and PostgreSQL was returned to its original stopped state. Existing migration
upgrade/downgrade, FORCE RLS, owner isolation, grants, immutable history and Phase 3A
regressions passed as part of the full suite. No new migration was added or run against
the shared database. No external provider was called.

No Flutter implementation changed, so this backend milestone did not rerun Flutter
analysis/tests/builds. Physical-device and live-provider results are not implied.

## Final review file set

The following 16 files are the complete unstaged/untracked review set, including the
original Chunk 6 work. The audit added only the justified expiry/erasure patches,
their regression coverage and relevant documentation. No unrelated work was discarded.

```text
AI_PIPELINE.md
API_SPEC.md
ARCHITECTURE.md
DATABASE_SCHEMA.md
DEVELOPMENT_PLAN.md
SECURITY.md
docs/adr/0007-phase-3b-synthetic-analysis.md
docs/PHASE_3B_CHUNK_6_AUDIT.md
packages/backend_domain/medlm_domain/report.py
services/api/medlm_api/analysis_report.py
services/api/medlm_api/analysis_repository.py
services/api/medlm_api/analysis_routes.py
services/api/medlm_api/main.py
services/api/medlm_api/medication_routes.py
services/api/tests/test_analysis_report.py
services/api/tests/test_manual_medication_api.py
```

Final index empty; HEAD unchanged at cdadf34. No staging, commit, push, reset, stash,
rebase, cleanup of existing work or Chunk 7 implementation occurred. The complete diff,
including new files, is available in ignored `.local/chunk6-review.patch` for review.

## Remaining gates and next action

Live Supabase/account/provider lifetime behavior, source licensing, production storage,
backup/restore/re-erasure, deployment TLS/CSP and maintenance scheduling remain unverified.
Physical Android/Web accessibility, human Hindi/Telugu translation review and iOS/desktop
validation are not established by this backend audit. No real medical uploads, evidence
lookup, provider calls, automatic medication creation, notifications or deployment enabled.

Review the complete uncommitted diff and this audit first. Stage/commit only after explicit
approval. Chunk 7 may start only after Chunk 6 is reviewed and committed; it remains the
fixture-only Flutter workflow and regression validation under ADR 0007.

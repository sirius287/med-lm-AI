# Phase 3A implementation and validation report

Date: 2026-10-05. Base commit: e5f071f. Phase 3A was committed as f064621, "Phase 3A: manual medication management and dose history". Post-commit working tree was clean.

Checkpoint reconciliation (2026-10-06): the approved review fixes use applied history dates and shared preview/activation materialization bounds. Fresh follow-up validation passed 100 backend tests (95 existing deprecation warnings), 98 Flutter tests, Flutter analysis, affected Python Ruff checks and git diff --check. Targeted suites passed 26 backend and 10 Flutter tests. Web/Android builds below predate those two fixes and were not rerun in the follow-up. No new validation was performed solely for this historical correction.

## Implemented scope

- Online-only Android/Web manual medication CRUD, list/detail and dashboard.
- Explicit timezone-aware daily, weekday, elapsed-interval and one-time schedules,
  signed preview/activation, immutable instruction/schedule snapshots and bounded materialization.
- Taken/skipped actions, append-only corrections, version conflicts and dose history.
- Removal with retained history or explicit active-database erasure; encrypted replay bodies
  erased and short-lived invalidated request tombstones prevent recreation through retry.
- Additive migration 0005, actual runtime-role ownership enforcement, replay encryption,
  expiry-only maintenance command/role and logout/write serialization.
- English/Hindi/Telugu interface strings, existing light/dark themes, keyboard/semantics,
  scalable layouts, session-owned in-memory state and safe partial-save/retry messages.
- Generated OpenAPI and response DTO bindings; original auth transport reused.

No AI, image/prescription processing, medicine-data integration, normal-app uploads,
notifications, offline queue, deployment or later phase has been implemented.

## Dependencies and contracts

Declared `tzdata` 2026.4 as a direct locked Python dependency; it was already installed transitively on Windows. Installed package metadata identifies the Python Software Foundation and Apache-2.0 license.
No Flutter dependency or SDK upgrade. No external model/provider request was made.
New server-only `MEDLM_MEDICATION_ENCRYPTION_KEY` protects replay responses and signs previews.
No populated secrets were added. The generator uses only Python standard-library tooling.

New routes: `/api/v1/medications` CRUD/detail; medication schedule preview/activation;
`POST /api/v1/occurrences/materialize`; `GET /api/v1/occurrences`; occurrence events;
`GET /api/v1/history`. Existing health/auth and injected synthetic-upload contracts remain.
See [ADR 0006](adr/0006-manual-medication-mvp.md) for exact bounds, failure and retention rules.

## Validation

Initial implementation validation, before the two approved review fixes (preserved historical results):

| Check | Actual result |
| --- | --- |
| Full backend suite, including real PostgreSQL | **97 passed, no skips**, 87.46 seconds; 92 existing deprecation warnings |
| Full Flutter suite | **97 passed**, including the original 79 foundation/auth/upload tests |
| Ruff | Passed for services, packages, database and the new generator |
| Flutter analysis | No issues found |
| Flutter Web build | Passed, 64.3 seconds; Wasm dry run also succeeded (not a Wasm release/browser validation) |
| Android debug APK | Passed, 13.7 seconds |
| Migration paths and runtime roles | Passed as part of backend suite; original migrations 0001–0004 unchanged |
| OpenAPI and generated response bindings | Parity tests/check passed |
| Git whitespace and unstaged-file whitespace | Passed; nothing staged |
| Disposable database cleanup | Zero leftover isolated databases; shared test medications/dose events both zero; test PostgreSQL stopped |

Artifacts: `apps/medlm/build/web/` and
`apps/medlm/build/app/outputs/flutter-apk/app-debug.apk` (ignored build output, not commit candidates).

Commands used during implementation and final validation:

```text
uv add tzdata
uv run alembic upgrade head (empty disposable local test database)
uv run ruff check services packages database scripts/generate_manual_client.py
uv run pytest -q --tb=short
uv run python scripts/export_contract.py
uv run python scripts/export_contract.py --synthetic
uv run python scripts/generate_manual_client.py
uv run python scripts/generate_manual_client.py --check
flutter gen-l10n
dart format <Phase 3A Dart files>
flutter analyze --no-pub
flutter test --no-pub --reporter expanded
flutter build web --no-pub
flutter build apk --debug --no-pub
git diff --check
```

Database tests use MEDLM_TEST_DATABASE_URL and MEDLM_MIGRATION_TEST_ADMIN_URL on the
existing loopback-only PostgreSQL cluster, port 15432. Migration tests create/drop their own
random empty databases. Shared medlm_test was verified to have no medical records before
upgrading; nothing was seeded into it. Existing migrations 0001–0004 were not edited.

Migration coverage: empty database, Phase 1 legacy record, and Phase 2 0004 paths;
round-trip of an empty new schema; guarded refusal to discard populated instruction history.
Authorization coverage includes real non-owner RLS, cross-owner foreign keys/API access,
CSRF, source/origin overrides, session revocation and a request paused before logout.
Concurrency tests cover conflicting terminal dose actions and idempotent materialization.
Scheduling tests cover boundaries, leap days, DST, explicit offsets, elapsed intervals,
effective cutoffs and deterministic randomized calendar properties across four timezones.

Implementation findings corrected before completion: Alembic revision identifier shortened
to fit its version column; nullable UUID SQL parameters explicitly cast; concurrent-test
client lifecycle corrected; controller reload after fast session restoration fixed; forms
keyed by account identity; corrections ordered by occurrence version; timezone data pinned
independently of host OS with path-like timezone inputs rejected before filesystem lookup;
stale medication versions block preview activation; history shows correction replacement
status; erased-record DELETE retries use expiring ownership tombstones. Test fixtures contain
synthetic values only.

## Environment and remaining verification

- Windows cannot validate iOS/macOS builds; desktop scope remains excluded.
- Initial PostgreSQL startup without its port override attempted 5432 and failed; restarting
  with the documented local port 15432 succeeded. No PostgreSQL configuration file changed.
- Backend tooling still emits existing Starlette/httpx and Alembic path-separator deprecations;
  unrelated dependency/configuration upgrades were not introduced.
- No live Supabase login/email delivery/remote revocation test. App login still needs provider
  configuration; local auth adapters are test-only, never a runtime bypass.
- No physical Android TalkBack, actual browser assistive-technology/manual UX review, or human
  Hindi/Telugu translation review. Automated checks and builds do not certify accessibility.
- No deployment, production signing, live data, production key rotation, scheduled maintenance,
  backup/restore-erasure drill, privacy/legal review or public-MVP readiness claim.
- Operation is online-only with no medication persistence on the client. No reminders are sent.
- Today/history use a labeled Asia/Kolkata display day, while schedule zones remain explicit.
- Key rotation intentionally fails closed on unreadable unexpired replay records; operational
  rotation and expiry scheduling must be settled before real-user release.

## Next step

Phase 3A review and commit are complete at f064621. Do not start notifications,
AI, deployment or another phase without a new approved scope. Before a real-user manual MVP,
validate live auth with synthetic accounts, reviewed translations, real devices/browsers,
maintenance/backup-erasure operations and the intended privacy/release controls.

## Exact file manifest

Commit f064621 included these 29 modified files and 35 new files. The list records the Phase 3A commit, not current working-tree status.

### Modified

- `AGENTS.md`
- `API_SPEC.md`
- `ARCHITECTURE.md`
- `DATABASE_SCHEMA.md`
- `DEVELOPMENT_PLAN.md`
- `README.md`
- `REQUIREMENTS.md`
- `SECURITY.md`
- `SETUP_WINDOWS.md`
- `apps/medlm/lib/app/app.dart`
- `apps/medlm/lib/auth/auth_controller.dart`
- `apps/medlm/lib/auth/auth_screen.dart`
- `apps/medlm/lib/core/api_client.dart`
- `apps/medlm/lib/l10n/app_en.arb`
- `apps/medlm/lib/l10n/app_hi.arb`
- `apps/medlm/lib/l10n/app_localizations.dart`
- `apps/medlm/lib/l10n/app_localizations_en.dart`
- `apps/medlm/lib/l10n/app_localizations_hi.dart`
- `apps/medlm/lib/l10n/app_localizations_te.dart`
- `apps/medlm/lib/l10n/app_te.arb`
- `config/backend.env.template`
- `contracts/openapi.json`
- `contracts/synthetic-openapi.json`
- `database/runtime_grants.sql`
- `pyproject.toml`
- `services/api/medlm_api/config.py`
- `services/api/medlm_api/main.py`
- `services/api/tests/test_database.py`
- `uv.lock`

### Created

- `apps/medlm/lib/medications/dashboard_screen.dart`
- `apps/medlm/lib/medications/generated/manual_models.dart`
- `apps/medlm/lib/medications/history_screen.dart`
- `apps/medlm/lib/medications/medication_controller.dart`
- `apps/medlm/lib/medications/medication_detail_screen.dart`
- `apps/medlm/lib/medications/medication_form_screen.dart`
- `apps/medlm/lib/medications/medication_list_screen.dart`
- `apps/medlm/lib/medications/medication_providers.dart`
- `apps/medlm/lib/medications/medication_service.dart`
- `apps/medlm/lib/medications/medication_shell.dart`
- `apps/medlm/lib/medications/schedule_editor.dart`
- `apps/medlm/test/manual_test_support.dart`
- `apps/medlm/test/medication_accessibility_test.dart`
- `apps/medlm/test/medication_controller_test.dart`
- `apps/medlm/test/medication_service_test.dart`
- `apps/medlm/test/medication_ui_test.dart`
- `database/medication_maintenance_grants.sql`
- `database/migrations/versions/0005_manual_medication_management.py`
- `docs/PHASE_3A_REPORT.md`
- `docs/adr/0006-manual-medication-mvp.md`
- `packages/backend_domain/medlm_domain/manual_medications.py`
- `packages/backend_domain/medlm_domain/scheduling.py`
- `scripts/generate_manual_client.py`
- `services/api/medlm_api/domain_idempotency.py`
- `services/api/medlm_api/medication_contracts.py`
- `services/api/medlm_api/medication_maintenance.py`
- `services/api/medlm_api/medication_repository.py`
- `services/api/medlm_api/medication_routes.py`
- `services/api/medlm_api/medication_service.py`
- `services/api/tests/test_dose_events.py`
- `services/api/tests/test_manual_contracts.py`
- `services/api/tests/test_manual_idempotency.py`
- `services/api/tests/test_manual_medication_api.py`
- `services/api/tests/test_manual_medication_schema.py`
- `services/api/tests/test_manual_scheduling.py`

Ignored `.local` validation helpers/logs and Flutter build artifacts are not commit candidates. No secrets or real medical data were added.

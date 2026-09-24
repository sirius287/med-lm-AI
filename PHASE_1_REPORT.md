# PHASE 1 REPORT

Date: 2026-09-24. Phase 1 foundation is implemented. This is not medical or production launch approval. Phase 2 has not started.

## 1. What was implemented

- Shared Flutter Android/iOS/web shell: startup/retry, GoRouter, Riverpod injection, configuration, API/error handling, fixed-event logging, placeholder Home/Settings, accessible Material controls with restrained neumorphic panels, system/light/dark themes and English/Hindi/Telugu resources.
- FastAPI health routes, `/api/v1`, explicit CORS, no-store responses, request IDs, sanitized errors/logs, database/service/repository boundaries.
- Supabase registration/login/logout/session adapters. Native secure token storage and authenticated API requests; encrypted server tokens and opaque HttpOnly web cookies; JWT signature/issuer/audience/expiry checks, provider identity check, local revocation, CSRF/Origin protection and serialized refresh. No auth UI or OAuth yet.
- PostgreSQL migration: users, profiles, medications, medication_schedules, dose_occurrences, dose_events, prescriptions, prescription_medicines, prescription_confirmations, medicine_analyses, verification_sources and private session/revocation tables. Owner RLS, composite ownership foreign keys and restricted grants; no seeded medical data.
- Internal image request, MIME/byte/pixel validation, decode/re-encode metadata removal, bounded owner-scoped temporary memory storage, expiry and deletion. No public upload endpoint or OCR.
- AI, vision, medicine identification/information and prescription interfaces; IN and disabled-US market policies. No model calls or medical implementations.
- Lockfiles, generated OpenAPI, setup docs and automated tests.

## 2. Files created

Full commit inventory: [docs/PHASE_1_FILES.txt](docs/PHASE_1_FILES.txt). Main additions: `apps/medlm`, `services/api`, `packages/backend_domain`, `database`, `contracts`, `config/backend.env.template`, `scripts`, `docs/adr`, reserved worker/infra/evaluation READMEs, pyproject.toml, uv.lock, alembic.ini, .python-version, .gitignore, README.md and SETUP_WINDOWS.md.

## 3. Files modified

All eight existing planning documents now distinguish the foundation from future design. ADR 0001 records the authorized phase expansion, `/api/v1`, provider-subject projection, email/password auth scope and deferred clinical invariants. The original documents were uncommitted and are included in this initial commit. See the inventory for generated platform and application files.

## 4. Dependencies added

Python: FastAPI, Uvicorn, pydantic-settings, SQLAlchemy, psycopg binary, Alembic, httpx, PyJWT/crypto, cryptography, Pillow, email-validator; development pytest/Ruff. Exact versions are in uv.lock.

Flutter: flutter_riverpod 2.6.1, go_router 17.5.0, http 1.6.0, supabase_flutter 2.17.2, flutter_secure_storage 11.2.0, Flutter localizations, intl 0.20.2 and standard Flutter test/lint packages. Exact transitive versions are in pubspec.lock. No Node dependencies. Upstream distribution license metadata is retained; formal release SBOM/license review remains required. No commercial medicine-data license is assumed.

Android build downloaded SDK Platform 35 revision 2 and build-cache artifacts; the package license was already accepted. No large framework reinstall was performed.

## 5. Commands executed

Environment checks: Flutter/Dart versions, `flutter doctor -v`, `uv python list --only-installed`, Python `-m pip --version`, Node/npm.cmd/Git/PostgreSQL versions, `adb devices`, `emulator -list-avds`, Windows port exclusion inspection and tool-path discovery.

Setup: `flutter create --platforms=android,ios,web --org ai.medlm --project-name medlm apps/medlm`, `flutter pub add` for the listed packages, `uv sync`, `flutter gen-l10n`, Dart format/fix and Ruff format/check.

Database: `initdb` in ignored `.local/pgdata`, `pg_ctl` startup, `createdb medlm_test`, `alembic upgrade head`, role/grant SQL via `psql -v ON_ERROR_STOP=1`, `alembic downgrade base`, `alembic upgrade head`, `alembic current`, offline `alembic upgrade head --sql`, grants reapplied and integration tests repeated. Isolated loopback port 15432 was used; the existing PostgreSQL service/database was not changed.

Validation: `uv run pytest -q`, `uv run ruff check services packages database`, `flutter analyze`, `flutter test`, `flutter build web`, `flutter build apk --debug`, `uv run python scripts/export_contract.py`, Uvicorn startup with `--no-access-log`, `Invoke-RestMethod` health call, Flutter web-server launch and Flutter Chrome launch. Exact reproducible commands are in SETUP_WINDOWS.md.

Git: ignore/secret/file review, staged whitespace check, and requested initial commit `Phase 1: project foundation`. No push or deployment.

## 6–8. Tests, results and builds

| Check | Result |
| --- | --- |
| Flutter analyze | PASS, no issues |
| Flutter tests | PASS, 4 tests: startup/retry, routing/theme, Hindi/Telugu and authenticated API/error behavior |
| Flutter web release build | PASS, apps/medlm/build/web |
| Android debug build | PASS, apps/medlm/build/app/outputs/flutter-apk/app-debug.apk |
| Chrome launch | PASS, debug service connected and application main started |
| Flutter web-server | PASS, server started |
| Backend tests with real PostgreSQL | PASS, 11 tests, no skips |
| Backend lint | PASS |
| Backend startup and actual health HTTP | PASS, status=ok, service=medlm-api, version=0.1.0 |
| Migration upgrade/downgrade/upgrade | PASS, head=0001_foundation; offline SQL generated |
| RLS/runtime role | PASS, two-user isolation, clinical tables denied; auth lifecycle tested under restricted role |
| iOS build | NOT RUN, requires macOS/Xcode |
| Native Windows/macOS | NOT BUILT/scaffolded in this phase |
| Live Supabase/OpenAI | NOT TESTED, no credentials supplied |

Backend tests cover invalid configuration, health/future-route absence, sanitized errors, auth origin/rate limits, JWT rejection cases, provider failures, decoded image validation, owner/expiry/delete behavior, real database connectivity, cookie/CSRF, encrypted refresh rotation and logout revocation. Synthetic auth-provider fixtures contain no medical information and do not prove live integration.

Initial tests found and corrected a Flutter theme font-size assertion, deprecated Supabase initialization argument, savepoint-test nesting and an incorrect assumption that provider tokens always contain expires_at. One upstream Starlette TestClient warning remains: httpx is deprecated in favor of httpx2. Tests pass; change test transport in a reviewed dependency update.

Browser automation reported no available browser surface: no screenshot or visual/assistive-technology inspection is claimed. Flutter launched Chrome and connected successfully. The startup check used port 8081; default API CORS allows 8080, so this was not a UI-to-API end-to-end check. The documented workflow uses 8080. No emulator/device was available for native execution.

## 9. Environment issues

Windows 11; Flutter 3.41.7/Dart 3.11.5; Android Studio/JBR Java 21, Android SDK 36.1.0. Some Android licenses remain unaccepted, but the debug APK succeeded. No AVD/device is configured/connected; no macOS/Xcode host.

Python 3.13.15 and pip 26.2.1 are installed outside PATH; uv discovers Python. Interpreter and SDK cache access required sandbox escalation. Node 24.18.0/npm 11.16.0 and Git 2.54.0 are available; npm.ps1 is blocked by execution policy, npm.cmd works. Node is not required.

PostgreSQL 18.6 exists outside PATH. Docker and Supabase CLI were not available on PATH and were not needed. Port 54329 is Windows-reserved; disposable PostgreSQL used 15432. Local trust authentication was confined to this synthetic test workflow, not recommended for deployment.

## 10. Security issues and limitations

No embedded keys, medical records or clinical outputs. Secret/env/build/cache directories are ignored; passwords are delegated to Supabase, not persisted by the application. Server tokens are encrypted; database parameter logging and raw medical/auth logging are suppressed.

Production still requires distributed abuse protection, private-session cleanup/key rotation, hardened decoding workers, durable image deletion, provider-account reconciliation, deployment TLS/CSP and release signing. Memory storage is a prototype: expiry does not prove secure erasure, and purge currently runs on access/explicit invocation. Clinical writes have no runtime grants until confirmation, immutable history, idempotency/outbox and reminder state machines exist. Generated icons remain placeholders; theme/locale preferences last for the running session only.

## 11. Remaining work

Validate real Supabase registration/email confirmation/redirects, asymmetric JWT signing, refresh/recovery/revocation and platform secure storage. OpenAI access must be verified in a later authorized synthetic evaluation. Procure India medicine rights/coverage and reviewer/processor/privacy decisions. Complete physical-device/iOS/accessibility checks, CI and operational controls. Future clinical schemas need typed validation and server-enforced confirmation before write endpoints are enabled.

## 12. Exact next recommended phase

**Phase 2: secure foundation completion and platform validation**, per ADR 0001: live authentication/platform checks, durable image lifecycle, CI/accessibility and production security boundaries; resolve India data/model/privacy dependencies. Medical AI, reports and prescription-to-reminder activation remain later phases. A new user instruction is required to start Phase 2.

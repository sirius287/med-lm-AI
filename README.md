# MedLM AI

[![Engineering preview checks](https://github.com/sirius287/med-lm-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/sirius287/med-lm-AI/actions/workflows/ci.yml)

MedLM is an **engineering preview** of an India-first medication-management app.
It records user-entered instructions and schedules; it does not diagnose,
prescribe, verify medicine identity or give medical advice. It is **not clinically
validated**. No public deployment has been verified.

## Current capabilities

| Capability | Actual boundary |
| --- | --- |
| Email/password accounts | Supabase identity; FastAPI browser sessions, HttpOnly cookies, CSRF, logout/revocation and expiry. Requires a configured development project and live validation. |
| Manual medications | Add/list/edit/delete, schedule preview/activation, today's doses, taken/skipped and append-only corrections/history. Online only, no notification delivery. |
| Shared Flutter client | Android/iOS/Web source, English/Hindi/Telugu, themes, keyboard/semantics and large-text tests. iOS requires macOS validation; native desktop is future work. |
| Synthetic analysis | Explicitly injected test harness only: registered fixtures, immutable extraction, mandatory transcription review and reports with all 24 medical values unavailable/null. Absent from normal app/API navigation. |
| Unavailable | Real medical uploads/OCR, live AI, medicine lookup/verification, patient medical reports, automatic medication creation, notifications, offline writes and deployment. |

Human transcription confirmation is not medical verification. Indian medicine-data
licensing and clinical release gates are unresolved. Never put real patient data,
credentials or private logs into public issues, fixtures, demos or screenshots.

## Run locally

Follow **[SETUP_WINDOWS.md](SETUP_WINDOWS.md)**, the authoritative beginner setup
guide with private prompts, isolated database provisioning and Chrome troubleshooting.
Use Flutter **3.41.7** / Dart **3.11.5**, Python **3.13**, PostgreSQL **18** and
uv **0.11.6**. Dependencies are locked. Android also needs Java/SDK; iOS needs
macOS/Xcode. Node and AI credentials are unnecessary.

~~~powershell
uv sync --frozen
uv run python scripts/dev.py init-db
uv run python scripts/dev.py configure-auth
uv run python scripts/dev.py check --database
~~~

The interactive initializer creates ONLY absent MedLM resources on localhost:5432,
applies the actual migration head and normal-runtime grants, and generates stable,
separate cryptographic keys without displaying them. It refuses existing
resources/settings. Owner credentials never enter the runtime .env.

Terminal A, repository root:

~~~powershell
$env:PYTHONPATH = 'services/api;packages/backend_domain'
uv run uvicorn medlm_api.main:app --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers
~~~

Terminal B:

~~~powershell
Set-Location apps/medlm
flutter pub get --enforce-lockfile
flutter run -d chrome --web-port 8080 --dart-define=API_BASE_URL=http://localhost:8000/api/v1
~~~

Settings load root .env when launched from the repository root; process variables
override it and empty placeholders are ignored. [.env.example](.env.example)
lists exact MEDLM_ names. The populated .env stays ignored. Do not use an owner
database URL at runtime or compile backend keys into Flutter. Native auth also
needs public SUPABASE_URL/SUPABASE_PUBLISHABLE_KEY Dart defines; web uses FastAPI.

GET /health is liveness, not readiness. Signed-out GET /api/v1/auth/session returns
the expected 401 authentication_required. Production requires HTTPS, secure cookies
and distinct encryption keys. JWT verification accepts ES256/RS256, not HS256.

## Repository and architecture

| Path | Purpose |
| --- | --- |
| apps/medlm | Flutter routing, Riverpod, shared UI and platform adapters |
| services/api/medlm_api | FastAPI, sessions, owner-scoped services/repositories |
| packages/backend_domain | Typed domain and medical-safety contracts |
| database/migrations | Single Alembic chain; current head 0009_human_review |
| database/runtime_grants.sql | Auth/manual-management grants only |
| contracts | Normal API and explicitly injected synthetic test contracts |
| scripts | Guarded setup, isolated tests, parity/security checks |
| docs/adr | Reviewed design decisions |
| infra | Deployment preparation, no provisioned cloud resources |

PostgreSQL is the source of truth. Runtime has no superuser, database/role creation,
RLS bypass or table ownership. Composite ownership, FORCE RLS, transactions,
idempotency and versions enforce isolation. Public hosting must serve Flutter
and /api/v1 through the **same HTTPS origin** for the existing same-site cookies.

See [architecture](ARCHITECTURE.md), [API](API_SPEC.md), [schema](DATABASE_SCHEMA.md),
[security](SECURITY.md), and [development plan](DEVELOPMENT_PLAN.md).
Historical phase reports retain their dated validation records.

## Validate and contribute

~~~powershell
uv run python scripts/test_backend.py --pg-bin 'C:\Program Files\PostgreSQL\18\bin'
uv run ruff check services packages database scripts
uv run ruff format --check services packages database scripts
uv run python scripts/check_localization.py
uv run python scripts/check_repository.py
Set-Location apps/medlm
flutter analyze
flutter test
flutter build web --release --dart-define=APP_ENV=production
flutter build apk --debug
~~~

The backend runner verifies a NEW disposable local cluster before any write;
existing services/databases remain untouched. Plain pytest without test URLs
skips database coverage. See the Windows guide/CI for contract parity commands.

The synthetic demonstration is an authenticated dependency-injected automated
workflow in Flutter/backend tests, not a public demo account or authentication
bypass. Physical-device accessibility and human translation review remain gates.

See [release checklist](docs/RELEASE_CHECKLIST.md), [deployment preparation](docs/DEPLOYMENT.md),
[contributing](CONTRIBUTING.md), [private security disclosure](.github/SECURITY.md),
and [release notes](CHANGELOG.md). Live auth and staging TLS/CORS/DB/browser checks
are not established by a successful web/APK build.

Source licensing awaits the owner's decision; publication alone grants no
open-source license. Dependency licenses are separate.

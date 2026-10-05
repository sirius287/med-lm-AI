# MedLM AI

India-first medication information and management application. **Phase 3A online manual management**: add/edit/remove medications, preview and activate schedules, view today’s doses, record taken/skipped actions and corrections, and view history. No AI, medicine identification, prescription processing, medical-image uploads or notification delivery is enabled. No medical records are seeded.

Shared Flutter Android/iOS/web client, FastAPI backend, PostgreSQL migrations and Supabase authentication adapters. All clinical and AI credentials belong on the backend. Windows/macOS are future native targets; web works as the desktop client in this phase.

## Repository

| Path | Purpose |
| --- | --- |
| `apps/medlm` | Flutter router, Riverpod DI, configuration, API/auth adapters, themes and en/hi/te localization |
| `services/api/medlm_api` | FastAPI application, authentication, database and image foundations |
| `services/api/tests` | Unit and PostgreSQL integration tests |
| `packages/backend_domain` | AI, source, repository and storage interfaces; disabled market policies |
| `database` | Alembic migration and least-privilege grants |
| `contracts/openapi.json` | Generated implemented API contract |
| `docs/adr` | Implementation decisions and scope changes |
| `scripts` | Contract export and local test-role setup |
| `services/worker`, `infra`, `evals` | Reserved future components, not implemented services |

## Prerequisites and setup

Validated SDKs: Flutter 3.41.7 / Dart 3.11.5, Python 3.13.15, uv and PostgreSQL 18.6. Android requires Android Studio, SDK/build tools, Java and accepted SDK licenses. iOS requires macOS/Xcode and signing. Node/npm are not needed to run this foundation.

See [SETUP_WINDOWS.md](SETUP_WINDOWS.md) for exact PowerShell commands, database roles, environments, backend/frontend startup and Android development. Dependencies are pinned in `uv.lock` and `apps/medlm/pubspec.lock`. Do not upgrade them independently without validation.

## Configuration

Copy `config/backend.env.template` to `.env` and populate only what is needed. Leave optional settings absent (remove blank URL/key lines) to run the health-only shell. `.env` and all `.env.*` files are ignored.

| Backend variable | Meaning |
| --- | --- |
| `MEDLM_ENVIRONMENT` | development, test or production |
| `MEDLM_DATABASE_URL` | Secret psycopg SQLAlchemy runtime connection; migration commands use owner connection |
| `MEDLM_SUPABASE_URL`, `MEDLM_SUPABASE_PUBLISHABLE_KEY` | Supabase project URL and public API key; never a service-role key |
| `MEDLM_SESSION_ENCRYPTION_KEY` | Fernet key protecting server-stored refresh/access tokens |
| `MEDLM_MEDICATION_ENCRYPTION_KEY` | Separate server-only Fernet key for 24-hour manual mutation replay |
| `MEDLM_CORS_ORIGINS` | JSON list of exact browser origins |
| `MEDLM_COOKIE_SECURE` | true in HTTPS production |
| `MEDLM_SESSION_TTL_SECONDS` | Absolute session lifetime, at most 86400 |
| `MEDLM_OPENAI_API_KEY`, `MEDLM_OPENAI_MODEL` | Reserved server-only configuration, no calls in Phase 1 |

Flutter compile-time settings: `API_BASE_URL`, `APP_ENV`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`. These are public values compiled into the app. Never put private keys in Dart defines. Browser defaults to same-origin `/api/v1`; development passes a backend URL. Native default `10.0.2.2` addresses the Android emulator host; physical devices and iOS need an explicit reachable URL. Only debug Android permits local HTTP.

## Implemented API

`GET /health` and `GET /api/v1/health` return `{"status":"ok","service":"medlm-api","version":"0.1.0"}`. This is liveness, not a promise that integrations are configured.

`POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `GET/DELETE /api/v1/auth/session` and authenticated `GET /api/v1/health/database` implement the auth foundation. Browser mutations require allowed Origin; authenticated cookie mutations also require X-CSRF-Token. Native clients use Supabase bearer tokens. Missing configuration fails closed. Supabase must use supported asymmetric JWT signing (ES256/RS256); legacy HS256 is deliberately unsupported. Enable email confirmation and configure approved confirmation redirects in Supabase. No OAuth callback/UI is implemented yet.

Manual `/api/v1/medications` CRUD, schedule preview/activation, `/occurrences/materialize`, `/occurrences`, dose events and `/history` are implemented. Domain POSTs require Idempotency-Key; medication PATCH/DELETE require If-Match. See [ADR 0006](docs/adr/0006-manual-medication-mvp.md). AI/prescription/normal upload endpoints stay absent. Generate contracts using `scripts/export_contract.py` and response bindings using `scripts/generate_manual_client.py`.

## Tests and limitations

Run `uv run pytest -q`; database tests require an explicitly configured disposable test database and runtime grants. Run Flutter `analyze`, `test`, `build web` and `build apk --debug` from `apps/medlm`. See [Phase 3A report](docs/PHASE_3A_REPORT.md) for current results and [PHASE_1_REPORT.md](PHASE_1_REPORT.md) for the historical baseline.

Live Supabase authentication still requires credentials and validation. OpenAI and medicine-data accounts are unnecessary for this manual-only slice. Before real-user release, validate live authentication, device/browser accessibility, reviewed translations, TLS/CSP, key rotation, maintenance scheduling, backup/restore and privacy/erasure operations. Phase 2 implements database-backed authentication throttling and an isolated synthetic upload harness; it does not enable clinical uploads. Local tests and builds are not production-readiness evidence.

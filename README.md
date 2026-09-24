# MedLM AI

India-first medication information and management application. **Phase 1 foundation only**: there is no medicine identification, medical advice, prescription processing or reminder functionality yet. No clinical records are seeded.

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
| `MEDLM_CORS_ORIGINS` | JSON list of exact browser origins |
| `MEDLM_COOKIE_SECURE` | true in HTTPS production |
| `MEDLM_SESSION_TTL_SECONDS` | Absolute session lifetime, at most 86400 |
| `MEDLM_OPENAI_API_KEY`, `MEDLM_OPENAI_MODEL` | Reserved server-only configuration, no calls in Phase 1 |

Flutter compile-time settings: `API_BASE_URL`, `APP_ENV`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`. These are public values compiled into the app. Never put private keys in Dart defines. Browser defaults to same-origin `/api/v1`; development passes a backend URL. Native default `10.0.2.2` addresses the Android emulator host; physical devices and iOS need an explicit reachable URL. Only debug Android permits local HTTP.

## Implemented API

`GET /health` and `GET /api/v1/health` return `{"status":"ok","service":"medlm-api","version":"0.1.0"}`. This is liveness, not a promise that integrations are configured.

`POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `GET/DELETE /api/v1/auth/session` and authenticated `GET /api/v1/health/database` implement the auth foundation. Browser mutations require allowed Origin; authenticated cookie mutations also require X-CSRF-Token. Native clients use Supabase bearer tokens. Missing configuration fails closed. Supabase must use supported asymmetric JWT signing (ES256/RS256); legacy HS256 is deliberately unsupported. Enable email confirmation and configure approved confirmation redirects in Supabase. No OAuth callback/UI is implemented yet.

Medicine, prescription, reminder and upload endpoints are not exposed. Their future behavior stays in API_SPEC.md and domain protocols. Generate the current OpenAPI using `scripts/export_contract.py`.

## Tests and limitations

Run `uv run pytest -q`; database tests require an explicitly configured disposable test database and runtime grants. Run Flutter `analyze`, `test`, `build web` and `build apk --debug` from `apps/medlm`. See [PHASE_1_REPORT.md](PHASE_1_REPORT.md) for actual results and limitations.

Live Supabase and OpenAI access require external credentials and separate validation. Production additionally requires a shared rate limiter, key rotation and session cleanup, audited image storage/deletion, deployment TLS/CSP and operational controls. In-memory image storage and per-process auth throttling are foundation components, not production infrastructure. Clinical table writes remain disabled until confirmation/state-machine invariants are implemented.

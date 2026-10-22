# Windows development setup

This is the authoritative local setup path. Run PowerShell from your checkout
(normally $env:USERPROFILE\source\medlm-ai). Never share passwords,
tokens, .env contents, cookies or health records in chat, logs or issues.

## Prerequisites

Use Flutter 3.41.7 / Dart 3.11.5, Python 3.13, uv 0.11.6 and PostgreSQL 18
(validation host: 18.6). Android also needs Java, Android Studio and its SDK.
iOS compilation/signing requires macOS/Xcode. Node, Docker and AI credentials
are unnecessary. Scripts do not download large SDKs or reset passwords.

For a new checkout only (skip cloning when you already have this repository):

~~~powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\source" | Out-Null
git clone https://github.com/sirius287/med-lm-AI.git "$env:USERPROFILE\source\medlm-ai"
~~~

~~~powershell
Set-Location "$env:USERPROFILE\source\medlm-ai"
git status --short
flutter --version
flutter doctor -v
uv --version
& 'C:\Program Files\PostgreSQL\18\bin\postgres.exe' --version
uv sync --frozen
~~~

## Initialize only a NEW MedLM database

Use the existing PostgreSQL service on 127.0.0.1:5432. You need its administrator
password privately. If unknown, stop and ask its administrator; do not guess/reset.
The root .env must not exist and MEDLM_DATABASE_URL must not be set in this
PowerShell process. Inspect configuration privately, never print it.

~~~powershell
uv run python scripts/dev.py init-db
~~~

The command privately prompts for the administrator password and two DIFFERENT
new passwords of at least 16 characters: medlm_owner and medlm_runtime.
Save the owner password in your password manager.

Preflight verifies the exact address, port, database postgres and role postgres,
then checks that medlm_dev and BOTH MedLM roles are absent. It refuses existing
objects without changing them. It never connects to ninecgpa_dev, ninecgpa_test,
urjavolt_db or another application's database.

After preflight, it creates only medlm_owner and medlm_runtime as LOGIN,
NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOREPLICATION, NOBYPASSRLS. Role DDL
contains SCRAM verifiers rather than plaintext passwords. It creates medlm_dev
from template0, owned by medlm_owner, and verifies it is empty before migrations.
It applies the existing Alembic chain to its actual head (0009_human_review),
checks the head, and applies ONLY database/runtime_grants.sql as owner.
Upload, analysis and maintenance grants are excluded.

The actual runtime login is checked for restricted attributes, manual table
grants, lack of clinical table access, no table ownership and FORCE RLS.
Only then is ignored root .env exclusively created, containing the runtime URL,
two independent Fernet keys and an independent rate-limit key. Keys are generated
locally without printing them. Existing keys are never overwritten or rotated.
The owner URL/password is never saved in .env.

Database creation is not transactionally reversible with role creation. If a later
step fails, resources remain intact: stop and inspect privately with your database
administrator. Do not drop roles or overwrite keys to force a retry.
This helper initializes a new database; it is not an upgrade/recovery command.

Protect the checkout/.env with your Windows account's filesystem permissions.
Do not use a shared writable checkout. Keep stable keys across restarts.
Rotation needs the planned procedure in ADR 0003, not a startup key replacement.

## Configure your DEVELOPMENT Supabase Auth project privately

For a dashboard walkthrough of an existing project, use
[SUPABASE_DEVELOPMENT.md](docs/SUPABASE_DEVELOPMENT.md). It explains current signing
key checks, private value entry and the default sender's team-address restrictions.

No script changes Supabase settings or creates accounts. In the correct project's
dashboard:

1. Verify project identity. Enable email/password Auth and KEEP email confirmation.
   Configure working development email delivery and respect email/abuse limits.
2. Set Auth Site URL to http://localhost:8080 and allow that exact confirmation
   redirect. Do not use wildcard production redirects.
3. Check JWT signing keys. This backend accepts ES256 or RS256 through JWKS and
   validates issuer, audience, expiry, subject and session. HS256 is deliberately
   unsupported. If your project uses HS256, plan Supabase's supported signing-key
   migration; never weaken backend verification.
4. Obtain the project HTTPS URL and current sb_publishable_ API key. Never use
   a secret or service-role key.

~~~powershell
uv run python scripts/dev.py configure-auth
uv run python scripts/dev.py check --database
git check-ignore .env
git status --short
~~~

Hidden local prompts append provider settings without changing encryption keys.
Existing provider values are not overwritten; correct them privately if necessary.
The command never contacts Supabase and does not prove live login works.

Backend variables all use MEDLM_: DATABASE_URL, SUPABASE_URL,
SUPABASE_PUBLISHABLE_KEY, SESSION_ENCRYPTION_KEY, AUTH_RATE_LIMIT_KEY are required
for complete browser auth. MEDICATION_ENCRYPTION_KEY is also required for manual
medication mutations. Full exact names appear in .env.example. Optional
MEDLM_SESSION_DECRYPTION_KEYS is a JSON list of up to three fallback Fernet keys.
The session lifetime cannot exceed 24 hours.

Development retains its existing session-key fallback for throttling, but this
procedure supplies an independent rate-limit key; production requires that key.
Never share email-confirmation links: they may contain authentication tokens.
After confirmation, navigate back to localhost:8080 yourself and sign in normally.

Settings load .env relative to the repository working directory. Process variables
override .env; empty placeholders are ignored. Never put an owner URL in runtime
configuration. check is offline; check --database is read-only and refuses any
target except the exact local medlm_runtime connection.

## Start FastAPI (terminal A, repository root)

~~~powershell
Set-Location "$env:USERPROFILE\source\medlm-ai"
$env:PYTHONPATH = 'services/api;packages/backend_domain'
uv run uvicorn medlm_api.main:app --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers
~~~

Startup diagnostics list missing variable NAMES, not values. Health is liveness
only; it can be 200 while login is unavailable. Do not expose this server publicly.

~~~powershell
Invoke-RestMethod http://127.0.0.1:8000/health
curl.exe -i http://localhost:8000/api/v1/auth/session
~~~

Expected: health 200 JSON; signed-out session 401 authentication_required JSON.
That 401 is correct when signed out.

## Start Flutter Web (terminal B)

~~~powershell
Set-Location "$env:USERPROFILE\source\medlm-ai\apps\medlm"
flutter pub get --enforce-lockfile
flutter gen-l10n
flutter run -d chrome --web-port 8080 --dart-define=API_BASE_URL=http://localhost:8000/api/v1
~~~

Use localhost consistently for browser/cookie hosts, not a mixture with 127.0.0.1.
Default CORS allows exact development origins; no wildcard is needed.
Web does not need Supabase keys compiled into Flutter: it uses FastAPI.

Open Account, register a test account you control, confirm email, then log in.
Registration returns 202/check-email; successful login returns 200 and an HttpOnly
opaque cookie. In DevTools Network verify calls reach localhost:8000/api/v1 and
return JSON, not the Flutter HTML fallback. Never share the cookie or request body.

Use clearly labelled synthetic text to exercise medication add/list/edit/delete,
schedule preview/activation, today's doses, taken/skipped, history and logout.
This records user instructions; it does not verify their medical correctness.

## Tests: use only disposable databases

~~~powershell
Set-Location "$env:USERPROFILE\source\medlm-ai"
uv run python scripts/test_backend.py --pg-bin 'C:\Program Files\PostgreSQL\18\bin'
uv run python scripts/test_backend.py --pg-bin 'C:\Program Files\PostgreSQL\18\bin' --setup-only
uv run ruff check services packages database scripts
uv run ruff format --check services packages database scripts
$env:PYTHONPATH = 'services/api;packages/backend_domain'
uv run python scripts/export_contract.py --check
uv run python scripts/export_contract.py --synthetic --check
uv run python scripts/export_contract.py --analysis --check
uv run python scripts/generate_manual_client.py --check
uv run python scripts/generate_analysis_client.py --check
uv run python scripts/generate_synthetic_catalog.py --check
uv run python scripts/check_localization.py
uv run python scripts/check_repository.py
uv run --with PyYAML==6.0.3 python scripts/check_release_config.py
git diff --check
Set-Location apps/medlm
flutter analyze
flutter test
flutter build web --release --dart-define=APP_ENV=production
flutter build apk --debug --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1
~~~

The backend runner creates a NEW SCRAM-protected cluster on a fresh loopback port
under ignored .local/test-runs/UUID. Before writes it verifies the actual data
directory, identity and empty database list. It ignores inherited application/test
URLs. It never contacts your existing service/databases. Fixtures create/drop
randomly named databases ONLY inside the disposable cluster. The runner stops
only its cluster; ignored synthetic data/logs remain for local inspection.
No shared medlm_test is needed. Never point tests at medlm_dev.

Without PostgreSQL binaries, plain uv run pytest -q with ALL database/test URLs
unset will skip integration tests. Skips are not passing database validation.

## Android and iOS

Use flutter doctor -v, accept SDK licenses yourself, and use Android Studio Device
Manager or a USB-debugging device. 10.0.2.2 reaches the host from an Android emulator.
Physical devices need a deliberately reachable host/firewall; do not expose the
development API publicly. Native auth additionally needs public SUPABASE_URL and
SUPABASE_PUBLISHABLE_KEY Dart defines for the same project. Backend secrets must
never appear in Dart defines. iOS requires a separate macOS/Xcode validation.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| 503 not_configured | Run scripts/dev.py check. Login needs encryption/DB plus Supabase; registration needs Supabase. Health is not readiness. |
| 503 database_unavailable | Privately check runtime URL, server, schema head and grants. Do not switch runtime to owner credentials. |
| 503 auth_unavailable | Check correct development project, networking, provider/email limits. Preserve fail-closed behavior. |
| 401 after login | Check email confirmation, project match and ES256/RS256. Never enable HS256. |
| HTML instead of JSON | Supply the exact API_BASE_URL above and restart Flutter. Inspect Request URL. |
| CORS/Origin rejection | Use consistent localhost hostnames and exact allowed origins. Preserve CSRF. |
| Cookie missing on HTTP | Local development uses MEDLM_COOKIE_SECURE=false; public HTTPS must use true. |
| Setup refuses existing objects | Stop and inspect with the administrator; never blindly drop objects or replace keys. |

See [deployment preparation](docs/DEPLOYMENT.md) before public testing.
No local build or synthetic fixture establishes clinical readiness.

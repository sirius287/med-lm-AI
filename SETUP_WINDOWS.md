# Windows setup

Use PowerShell from the repository root. Do not install another SDK if one is already present. Installation of Flutter, Android Studio, PostgreSQL and Python is a separate machine setup step; these large tools are not downloaded by repository setup scripts.

## Inspect tools

```powershell
git --version
flutter --version
dart --version
flutter doctor -v
uv --version
uv python list --only-installed
node --version
npm.cmd --version
& "$env:LOCALAPPDATA\Android\sdk\platform-tools\adb.exe" devices
& "$env:LOCALAPPDATA\Android\sdk\emulator\emulator.exe" -list-avds
```

On this machine Flutter is `C:\src\flutter\bin`; Python 3.13 is discovered by uv even though `python`/`pip` are not on PATH. `npm.cmd` avoids the local PowerShell script execution-policy restriction. Flutter SDK bin must be on PATH in a new shell. Review Android licenses using `flutter doctor --android-licenses`; accepting them is your decision. Create an AVD using Android Studio Device Manager or attach a USB-debugging device.

## Python dependencies and configuration

```powershell
uv sync --frozen
Copy-Item config/backend.env.template .env
notepad .env
```

Remove empty optional URL/key settings to start without integrations. For authentication, supply your Supabase project URL and publishable key, and generate a private session-encryption key locally:

```powershell
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Put the generated value in `.env`, never in Flutter or git. Production requires HTTPS, secure cookies and configured authentication. Keep migration-owner credentials separate from runtime credentials.

## PostgreSQL

Use an empty development database, not an existing application database. The following commands assume PostgreSQL 18 and an installed local server on port 5432; adjust port/path for your installation. PostgreSQL prompts for passwords. No passwords are embedded in these commands.

```powershell
$pgBin = 'C:\Program Files\PostgreSQL\18\bin'
& "$pgBin\createuser.exe" -h 127.0.0.1 -U postgres --pwprompt medlm_owner
& "$pgBin\createdb.exe" -h 127.0.0.1 -U postgres -O medlm_owner medlm_dev
& "$pgBin\createuser.exe" -h 127.0.0.1 -U postgres --pwprompt --no-superuser --no-createdb --no-createrole medlm_runtime
$env:MEDLM_DATABASE_URL = Read-Host 'Owner SQLAlchemy URL: postgresql+psycopg://medlm_owner:URL_ENCODED_PASSWORD@127.0.0.1:5432/medlm_dev'
uv run alembic upgrade head
uv run alembic current
& "$pgBin\psql.exe" -h 127.0.0.1 -U medlm_owner -d medlm_dev -v ON_ERROR_STOP=1 -f database/runtime_grants.sql
Remove-Item Env:MEDLM_DATABASE_URL
```

Set `.env` MEDLM_DATABASE_URL to the **medlm_runtime** connection before starting the API. The role must have NOBYPASSRLS and must not own tables. In Supabase, arrange equivalent private-schema grants with your database administrator; do not expose these schemas to anon/authenticated Data API roles. Do not run `scripts/test_role.sql` against production.

## Run backend

For Chunk 2, apply migrations through `0003_auth_session_hardening`, then reapply `database/runtime_grants.sql` with the owner account. Upload grants remain absent. Set `MEDLM_AUTH_RATE_LIMIT_KEY` to an independent random secret (at least 32 characters) shared across API instances; production requires it. Optional `MEDLM_SESSION_DECRYPTION_KEYS` is a JSON array of up to three previous Fernet keys. Never retire old keys before sessions are rewritten or their original maximum lifetime elapses. See ADR 0003 for rotation and legacy-session limitations.

```powershell
$env:PYTHONPATH = 'services/api;packages/backend_domain'
uv run uvicorn medlm_api.main:app --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers
```

In another terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
```

Use `--host 0.0.0.0` only when intentionally allowing a physical device on a trusted local network, with appropriate Windows firewall rules. Never expose the development server publicly.

## Flutter web and Android

```powershell
Set-Location apps/medlm
flutter pub get
flutter gen-l10n
flutter run -d chrome --web-port 8080 --dart-define=API_BASE_URL=http://localhost:8000/api/v1
```

For Android, start an emulator/device, then run in a separate terminal:

```powershell
Set-Location apps/medlm
flutter devices
flutter run -d DEVICE_ID --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1
flutter build apk --debug
```

Replace DEVICE_ID with `flutter devices` output; physical devices need your host's LAN address instead of 10.0.2.2. Native authentication additionally needs public `--dart-define=SUPABASE_URL=...` and `--dart-define=SUPABASE_PUBLISHABLE_KEY=...`. There is no sign-in screen in Phase 1. iOS must be built/tested on macOS with Xcode; generated files on Windows are not proof of an iOS build. Release signing is not configured.

## Tests and contracts

Optional bounded session maintenance (root directory, runtime database URL, no provider call):

```powershell
$env:PYTHONPATH = 'services/api;packages/backend_domain'
uv run python -m medlm_api.session_maintenance --batch-size 500
```

This removes expired browser sessions/throttle buckets only; provider-session revocation tombstones are retained. No automatic maintenance schedule is installed. Migration/auth integration tests also need `MEDLM_MIGRATION_TEST_ADMIN_URL` pointing to a disposable local cluster with database/role creation privileges; they create/drop their own randomly named databases. Never point this variable at production.

From repository root:

```powershell
uv run pytest -q
uv run ruff check services packages database
$env:PYTHONPATH = 'services/api;packages/backend_domain'
uv run python scripts/export_contract.py
Push-Location apps/medlm
flutter analyze
flutter test
flutter build web
Pop-Location
```

For integration tests create a separate empty disposable database (`medlm_test`), migrate it with its owner URL, and run test-role/grant setup using an administrator. The test connection needs permission to SET ROLE medlm_runtime. Never use a database containing real users or medicines: tests assert clinical tables are empty.

```powershell
$env:MEDLM_DATABASE_URL = Read-Host 'Disposable test database owner URL'
uv run alembic upgrade head
# Adjust these psql connection arguments to that same disposable database.
& "$pgBin\psql.exe" -h 127.0.0.1 -U postgres -d medlm_test -v ON_ERROR_STOP=1 -f scripts/test_role.sql -f database/runtime_grants.sql
& "$pgBin\psql.exe" -h 127.0.0.1 -U postgres -d medlm_test -v ON_ERROR_STOP=1 -c 'GRANT medlm_runtime TO medlm_owner'
$env:MEDLM_TEST_DATABASE_URL = $env:MEDLM_DATABASE_URL
uv run pytest -q
Remove-Item Env:MEDLM_TEST_DATABASE_URL
Remove-Item Env:MEDLM_DATABASE_URL
```

Without MEDLM_TEST_DATABASE_URL, database tests explicitly skip. Migration downgrade destroys the application schemas: use only a disposable database for round-trip validation. Do not run downgrade against live data.

## Chunk 4 account UI validation

Home now opens Account for email/password registration, sign-in and sign-out. Home and Settings remain accessible without an account. Existing native Supabase configuration and Web backend cookie/CSRF configuration still apply; this chunk does not provision a provider or credentials. An unavailable provider/configuration displays an unavailable state. Registration instructions do not prove email delivery. Use synthetic accounts only during authorized integration validation.

From `apps/medlm`, run `flutter test test/auth_controller_test.dart test/auth_ui_test.dart` for the new controller/UI checks. The full `flutter test` suite also retains the previous authentication and synthetic upload adapter tests. Run `flutter build apk --debug` for the Android build in addition to the Web command above.

Before release, manually check Android TalkBack and browser screen-reader reading order, status announcements, keyboard focus, software-keyboard layout and 200% text/zoom in both themes and all three languages. Obtain human review of Hindi/Telugu UI copy. Automated widget accessibility tests and successful builds do not replace these checks or validate live provider behavior. iOS and desktop remain unvalidated in this chunk.

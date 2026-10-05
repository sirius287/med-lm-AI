# Local synthetic storage validation (Windows)

Use only the existing disposable PostgreSQL cluster and generated nonmedical fixtures. No Supabase/OpenAI credentials are needed. The normal app does not accept uploads. Tests explicitly construct the enabled harness and allowlist generated image hashes; there is no environment-only switch that enables routes.

From the repository root, after starting the isolated cluster on port 15432:

```powershell
$env:MEDLM_DATABASE_URL = 'postgresql+psycopg://medlm_owner@127.0.0.1:15432/medlm_test'
$env:MEDLM_TEST_DATABASE_URL = $env:MEDLM_DATABASE_URL
$env:MEDLM_MIGRATION_TEST_ADMIN_URL = $env:MEDLM_DATABASE_URL
uv run alembic upgrade head
uv run pytest -q
uv run ruff check services packages database
$env:PYTHONPATH = 'services/api;packages/backend_domain'
uv run python scripts/export_contract.py --synthetic
Push-Location apps/medlm
flutter analyze
flutter test
flutter build web
flutter build apk --debug
Pop-Location
```

The role/migration test harness prepares the separate restricted upload worker role and grants in randomly named disposable databases. It does not grant upload access to the ordinary application database. It requires the existing `medlm_runtime` role described in SETUP_WINDOWS.md. Never supply a production/admin application URL to these test variables.

For an operator-managed **synthetic harness only**, provision `medlm_upload_worker` separately with `NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS` and its own login credential, then apply `database/synthetic_upload_grants.sql` as migration owner. Never give API credentials membership in the worker role. Run all three independent commands with the same protected storage root/key and a worker-role DB URL:

```powershell
$env:MEDLM_ENVIRONMENT = 'test'
$env:MEDLM_UPLOAD_WORKER_DATABASE_URL = Read-Host 'Restricted disposable upload-worker database URL'
$env:MEDLM_SYNTHETIC_STORAGE_ROOT = (Join-Path (Get-Location) '.local/synthetic-objects')
# Set MEDLM_SYNTHETIC_STORAGE_KEY through protected local environment provisioning.
# It must be a separate Fernet key, identical for the harness and maintenance processes.
uv run python -m medlm_api.upload_maintenance deletion_worker
uv run python -m medlm_api.upload_maintenance independent_sweep
uv run python -m medlm_api.upload_maintenance reconciliation
```

Each command runs once, prints only summary counts and exits nonzero for failed/overdue deletion. For supervised independent processes, each accepts `--loop --interval 60` (maximum interval 300 seconds). Do not combine them into one failure-dependent queue. The chunk supplies commands, not an installed task/service or live alerting configuration. In a test harness, run all three successfully before requesting an intent; admission fails after five minutes without fresh successful evidence.

Restrict both the object directory and its sibling `.deletion-ledger` directory to the service OS account using Windows ACLs. Keep the encryption key out of git/logs/frontend. Encryption is not an ACL or a promise of physical sector erasure. Exclude images from backups; keep the deletion ledger independent of DB/image restore snapshots. Never delete a nonempty ledger to make health checks pass.

Restore drill: disable all access, preserve the current independent ledger, restore the disposable DB/objects, run reconciliation and independent sweep, then all three health checks. Do not restore an older ledger. The automated regression test restores encrypted object bytes and removes the DB receipt relation to exercise re-erasure; provider backup/region behavior remains unvalidated.

Failure handling: leave admission disabled; repair storage access/key/worker health; rerun reconciliation and sweep before restarting admission. Do not shorten retention metadata or manually mark objects purged. Existing receipts are retained through their original 90-day expiry, exceeding the proposed 30-day backup window. Real medical uploads remain prohibited after the drill.

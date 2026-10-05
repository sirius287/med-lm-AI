# Phase 2 chunk 1: scope/contracts and database

Date: 2026-09-25. Implemented only the approved database foundation. No commit created. Phase 2 as a whole is not complete.

## Changes

New migration `0002_synthetic_uploads` depends on unchanged `0001_foundation`. It adds six private tables: uploads, upload_objects, upload_deletion_jobs, upload_audit_events, upload_deletion_receipts and upload_safeguard_runs. Includes owner-consistent foreign keys, FORCE RLS, bounded retention/ticket metadata, immutable object identifiers and accepted checksums, guarded lifecycle transitions, lease/fencing metadata, expiry/job indexes, minimal audit/deletion receipts and nonpersonal maintenance-run summaries.

No API/worker grants are added. No clinical data, bytes, source records or runtime integrations are seeded. Existing tables, auth routes, application code, public contracts and frontend are unchanged. Existing backend connectivity test now resolves Alembic head rather than hardcoding the Phase 1 revision.

Downgrade removes only the new objects and is intentionally blocked by unpurged inventory or unexpired deletion receipts. Once permitted, it drops Phase 2 metadata; it is not a data-preserving rollback. Ordinary user deletion cannot discard unpurged inventory; future erasure must purge before deleting its metadata. Existing Phase 1 identities with no uploads retain their previous behavior.

## Validation performed

Used the existing isolated PostgreSQL 18 test cluster on loopback port 15432, not the installed application database. Applied the draft migration to `medlm_test`. The migration test harness created and removed nine randomly named disposable databases across its test cases; all image-related fixtures were metadata only. No storage objects or real images were created.

Commands executed from repository root, with local test URLs supplied only through environment variables:

```powershell
uv run alembic upgrade head
uv run alembic downgrade 0001_foundation
uv run alembic upgrade head
uv run ruff format database/migrations/versions/0002_synthetic_uploads.py services/api/tests/test_upload_schema.py
uv run ruff check services packages database
uv run pytest -q
git diff --check
```

Tests require both `MEDLM_TEST_DATABASE_URL` (migrated empty clinical test database) and `MEDLM_MIGRATION_TEST_ADMIN_URL` (disposable cluster admin connection). The latter must allow temporary database/role creation and SET ROLE; use the existing `scripts/test_role.sql` in that cluster to prepare medlm_runtime if absent. Never use production credentials. Without these explicit settings the corresponding tests skip and do not establish database validation.

Result: **20 tests passed, no skips; Ruff and whitespace checks passed.** Existing Starlette/httpx deprecation and Alembic path_separator deprecation warnings remain; neither is a test failure and no dependency update was made.

- Empty database -> head -> Phase 1 -> head: passed.
- Phase 1 schema with synthetic account/profile/revocation data -> head -> Phase 1 -> head: passed; original column definitions and records preserved.
- Existing backend/authentication/image tests: passed.
- API role denied new-table access; missing owner context and cross-owner reads/writes rejected under temporary non-owner/non-BYPASSRLS role: passed.
- Upload size/TTL/purpose constraints, immutable metadata, composite job ownership and audit immutability: passed.
- Purge prerequisites, unexpired receipt preservation, retention nonextension and account cascade ordering: passed.
- Lease/fencing constraints and two-connection cancellation/object-registration serialization: passed.
- Unsafe downgrade refuses and rolls back its temporary RLS changes: passed.

This does not validate physical deletion, object storage, workers, authentication changes, UI, CI or external services. Those remain separate authorized chunks. The normal application still has no upload endpoints.

## Exact changed files

Added:
- `database/migrations/versions/0002_synthetic_uploads.py`
- `services/api/tests/test_upload_schema.py`
- `docs/adr/0002-phase-two-scope-and-upload-schema.md`
- `docs/PHASE_2_CHUNK_1_REPORT.md`

Modified:
- `AGENTS.md`
- `API_SPEC.md`
- `ARCHITECTURE.md`
- `DATABASE_SCHEMA.md`
- `DEVELOPMENT_PLAN.md`
- `services/api/tests/test_database.py`

Documentation changes only reconcile current scope, canonical `/api/v1`, completed Phase 1 status and the implemented database subset. Historical Phase 1 report and ADR remain preserved.

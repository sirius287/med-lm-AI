# Phase 2 Chunk 3: secure synthetic storage and uploads

Date: 2026-09-26. **Implemented and locally validated within the approved synthetic-only scope.** No commit created; Chunk 4 was not started. Phase 2 as a whole is not declared complete.

## Implemented

- Explicit test-harness upload creation, bounded content transfer, completion, status, authenticated preview, deletion and receipt APIs. Normal-app upload routes remain absent; production/development harness injection is rejected.
- Server-controlled synthetic checksum allowlist, notice acknowledgement, immutable source checksum, idempotency, five-minute hash-only single-use tickets, per-owner quotas and version preconditions.
- Reuse of actual auth/session/CSRF validation and transaction-local ownership. Session revocation and final storage writes share a transaction lock; browser principals respect the earlier provider/app expiry. Existing auth routes and response shapes remain unchanged.
- Encrypted local storage with owner binding, exclusive opaque keys, no persistent original images/filenames/plaintext spool, decoding/metadata stripping and authenticated no-store PNG preview. Durable inventory precedes filesystem writes.
- Independent deletion worker, expiry sweep and physical inventory/receipt reconciliation, available as separate bounded command processes. Persistent job leases/fencing, retry handling, actual absence verification and fail-closed deletion-health admission.
- A separate encrypted deletion ledger that survives DB/image snapshot restoration when preserved as required. Restored bytes remain unreadable and are re-erased. Receipts contain no image hash/content; account erasure can null their user link.
- Flutter synthetic adapter for authenticated binary upload, immutable completion, status, versioned deletion, receipt polling and bounded preview retrieval. It distrusts returned upload URLs, refuses redirects, clears its temporary buffer on failure/session invalidation and drops late results. No normal-app upload screen/picker/provider was enabled.

Review [ADR 0004](adr/0004-synthetic-upload-runtime.md), [synthetic API contract](../contracts/synthetic-openapi.json) and [Windows validation runbook](runbooks/synthetic-upload-validation.md) for precise contracts and limits.

## Database changes

Migration `0004_upload_runtime` follows 0003. It adds nullable immutable request key/hash/source checksum columns and owner/request uniqueness, plus narrowly scoped maintenance policies and an API health-read policy. Legacy rows remain usable by their earlier schema. Upgrade/downgrade/re-upgrade preserved existing upload values in tests; downgrade discards only the new request metadata/policies.

Optional `database/synthetic_upload_grants.sql` supplies column-level API updates and table-specific worker permissions only in a disposable harness database. The API cannot write purge markers, complete deletion jobs or insert receipts. Worker tests use the actual non-owner/non-BYPASSRLS role and prove denial of auth-table access. Default runtime grants and migrations 0001/0002/0003 were not changed.

Retention: default harness image expiry one hour, configurable only within 24 hours; transfer ticket five minutes; non-review completion/cancellation queues earlier deletion. Audit/receipts expire at 90 days and safeguard summaries at 30 days. Deleted upload metadata is cleaned after 90 days. The independent receipt ledger must not be rolled back with image/database snapshots. Scheduled execution is necessary to enforce deletion; a timestamp alone is not a guarantee.

## Validation results

| Validation | Final result |
| --- | --- |
| `uv run ruff check services packages database` | Passed |
| Full `uv run pytest -q --tb=short` | **64 passed, no skips**, 67 deprecation warnings; 60.39 seconds |
| New upload-specific tests | **28 passed**, included in the full suite |
| Existing foundation/auth/schema regressions | **36 passed**, included in the full suite |
| Migration 0004 | Applied to local disposable `medlm_test`; empty-to-head, prior-schema, existing-row preservation and downgrade/re-upgrade tested |
| Normal and synthetic OpenAPI parity | Passed; normal `contracts/openapi.json` unchanged |
| `flutter analyze` | Passed, no issues |
| `flutter test` | **16 passed**, including 7 new synthetic adapter tests |
| `flutter build web` | Passed; `apps/medlm/build/web` |
| `flutter build apk --debug` | Passed; `apps/medlm/build/app/outputs/flutter-apk/app-debug.apk` |
| `git diff --check` | Passed; Windows line-ending notices only |

Backend coverage includes every harness ownership boundary, missing-owner RLS context, runtime/worker privilege separation, CSRF/preflight, ticket replay/expiry, idempotency conflicts, quota enforcement, MIME/size/decoding/pixel rejection, JPEG/WebP-to-PNG sanitization, actual streamed-body timeout, encrypted adapter reopening, interrupted disk write cleanup, cancellation and concurrent logout/write ordering, failed deletion/receipt storage, durable retry fences, independent sweeps, restored bytes/missing DB receipts and execution of all three maintenance modes as separate Python processes.

The ordinary app's upload denial is tested. Synthetic provider fixtures are used only at the test network boundary; there is no application test-auth bypass. No medicine identification, medical records, prescriptions, medical claims or live API responses were fabricated.

Validation commands also included `uv run alembic upgrade head`, `uv run python scripts/export_contract.py --synthetic`, targeted upload pytest runs, Ruff/Dart formatting and git status/diff inspection. The tests used local PostgreSQL 18 at `127.0.0.1:15432`, through `MEDLM_TEST_DATABASE_URL` and `MEDLM_MIGRATION_TEST_ADMIN_URL`. They created/dropped randomly named disposable databases. No installed application database was migrated and no HTTP application server was launched.

Testing caught and corrected a receipt timestamp exceeding its strict 90-day bound by microseconds, and unnecessary update-lock permissions in immutable-ledger cleanup. The failed permissions run was interrupted; its 15 inactive temporary databases were removed after validation. The final temporary-database count was **zero**, and the isolated cluster was stopped. The restricted NOLOGIN test worker role remains available in that disposable cluster.

## Exact files created by Chunk 3

- `services/api/medlm_api/uploads.py`
- `services/api/medlm_api/upload_routes.py`
- `services/api/medlm_api/upload_storage.py`
- `services/api/medlm_api/upload_maintenance.py`
- `services/api/tests/test_upload_runtime.py`
- `database/migrations/versions/0004_upload_runtime.py`
- `database/synthetic_upload_grants.sql`
- `apps/medlm/lib/uploads/synthetic_upload_service.dart`
- `apps/medlm/test/synthetic_upload_test.dart`
- `contracts/synthetic-openapi.json`
- `docs/adr/0004-synthetic-upload-runtime.md`
- `docs/runbooks/synthetic-upload-validation.md`
- `docs/PHASE_2_CHUNK_3_REPORT.md`

## Exact files modified by Chunk 3

- `services/api/medlm_api/auth.py`
- `services/api/medlm_api/main.py`
- `apps/medlm/lib/core/api_client.dart`
- `scripts/export_contract.py`
- `contracts/README.md`
- `AGENTS.md`
- `API_SPEC.md`
- `DATABASE_SCHEMA.md`
- `DEVELOPMENT_PLAN.md`
- `SECURITY.md`
- `SETUP_WINDOWS.md`

Accepted Chunk 1 files/changes remain uncommitted and preserved, including migration 0002 and its test fixture. `ARCHITECTURE.md` and `services/api/tests/test_database.py` remain dirty from that earlier chunk, not this implementation. Dependency manifests/lockfiles were unchanged; **no dependencies were added or upgraded**. Local test logs/cleanup helpers and build outputs are ignored artifacts, not source changes.

## Remaining limits

- No live Supabase Storage/Auth, OpenAI, external credentials, provider retention guarantee or cloud integration was exercised. Storage is a local encrypted adapter behind an interface.
- No real clinical uploads are enabled. The Flutter adapter is exercised in tests and is deliberately not registered in normal UI. Device/browser end-to-end upload UI and physical secure-storage behavior are not claimed.
- The three commands are implemented and tested independently, but no Windows scheduled service, production monitoring or alert delivery was installed. Run them independently at least every five minutes; the 15-minute purge objective is an operational target, not a proven deployed SLA.
- Local storage uses serialized DB-fenced IO and bounded directory enumeration; production-scale performance, hardened codec isolation, filesystem ACL deployment, encryption-key rotation/recovery and managed backup drills remain release work. A deleted file/receipt proves local namespace absence, not physical-sector erasure.
- Preserve the independent ledger through restores. The tested restore simulation is not a full managed-provider disaster-recovery validation. Losing/rolling back both the DB and independent ledger requires keeping access disabled pending recovery.
- Starlette/httpx and Alembic path-separator deprecations remain. Flutter reported newer dependencies outside current constraints; no upgrade was needed. Initial PostgreSQL default-port startup failed; explicitly using the existing isolated port 15432 resolved it.
- iOS/desktop were not built or tested. Full Phase 2 acceptance, including later UI/accessibility/operational work, remains outstanding.

## Next step

Stop for user review of Chunk 3 results. Do not begin Chunk 4 or create a commit without a new instruction. Any eventual commit plan must account for the still-uncommitted accepted Chunk 1 prerequisites.

# Phase 2 acceptance scope and upload schema

Date: 2026-09-25. Status: scope approved; only contracts and database chunk authorized for implementation. Supersedes conflicting future-phase wording in ADR 0001 and historical plan sections. Phase 1 commit 3b59d92 remains the baseline.

## Approved scope

Phase 2 requires Android and Web only. iOS/native desktop and OAuth are out of scope; retain email/password and defer PKCE to future OAuth. Live provider validation may remain explicitly pending without credentials. Real clinical uploads remain disabled. Later Phase 2 chunks cover auth UI/security, durable synthetic storage/deletion, Android/Web accessibility, CI and operational validation; none of those implementations are authorized in this chunk.

Local Phase 2 completion requires backend/regression/security tests; additive migration tests; Android/Web builds and execution; synthetic-provider authentication and secure-storage/cookie/CSRF tests; durable synthetic upload/restart/deletion/race tests; independent reconciliation; normal-app upload denial; accessibility/localization checks; contract/security checks; reproducible validation and a report distinguishing live-service gaps. This database chunk is not full Phase 2 completion.

## Chunk 1 contract

Migration `0002_synthetic_uploads` adds only private metadata. No existing table, column, grant, auth/API behavior or migration is modified. There are no ORM models in Phase 1: Alembic SQL remains the schema authority. No storage adapter, worker, route, feature flag, provider call or frontend change is introduced. The existing OpenAPI artifact remains unchanged.

| Table | Purpose |
| --- | --- |
| `medlm.uploads` | Owned upload intent; immutable synthetic-purpose and notice acknowledgement; declared kind/MIME/size; hashed ticket; consumption timestamp; bounded retention; lifecycle/version |
| `medlm.upload_objects` | Inventory of original/sanitized/review/spool objects using opaque UUID keys, optional pinned checksum/size and purge timestamps; no bytes, filenames, URLs or filesystem paths |
| `medlm.upload_deletion_jobs` | One durable deletion job per object; owner-consistent FK, retry availability, lease token/expiry, monotonic fencing/attempt counters and enumerated failures |
| `medlm.upload_audit_events` | Immutable events with enumerated codes, owner and upload references; bounded retention, no free-text payload |
| `medlm.upload_deletion_receipts` | Minimal object-key/verification-time ledger surviving owner deletion with user link nulled; explicit bounded expiry, no image hash/content |
| `medlm.upload_safeguard_runs` | Nonpersonal run summaries for worker/sweeper/reconciliation health and overdue counts; no worker is implemented |

Notice acknowledgement is embedded in the immutable upload record, rather than adding an unused general-purpose consent subsystem. It is not legal approval for medical processing. `purpose='synthetic_validation'` is a constrained provenance label, not an authorization mechanism or a detector of clinical content. Real images must never be submitted in this phase.

## Authorization and integrity

All new tables enable FORCE RLS. Owned tables require transaction-local `app.user_id`; missing context denies access. Safeguard runs have no ordinary-row policy (default deny). No new grants are given to medlm_runtime or PUBLIC. Tests grant DML to a temporary non-owner/non-BYPASSRLS role inside a rolled-back transaction to exercise RLS separately from the default privilege denial. Existing Phase 1 auth grants remain unchanged.

Cross-owner relationships use composite FKs. Invoker triggers protect immutable identity/object metadata, irreversible lifecycle transitions, nonextending retention and consumed tickets. Object inventory registration locks the parent upload, preventing new registration after cancellation/expiry. Future workers must still compare lease/fencing tokens and current state in conditional writes immediately before storage operations; the schema alone cannot fence external writes.

No role/queue-claim function is provisioned for cross-user workers. Such functions and narrowly scoped maintenance policies require the subsequent worker review. Do not give workers generic BYPASSRLS or owner credentials. SQL triggers are not callable public operations.

## Retention and deletion

- Ticket expiry is at most five minutes; upload retention is at most 24 hours from creation. Processing completion/cancellation may require earlier deletion. Object expiry cannot exceed parent expiry when registered. Future access/sweeper queries must use the earlier parent/object expiry and any deletion request, not an object timestamp alone.
- Retries cannot update upload expiry or object keys. Accepted checksum/size and consumed-ticket timestamps cannot be replaced. Review objects require the original retain-for-review choice.
- Unpurged inventory blocks object/upload metadata deletion, including account cascades. Future account deletion must disable access, purge objects and then remove rows. Existing Phase 1 accounts with no uploads are unaffected. This implements the existing architecture's purge-before-completion requirement, not a complete account-erasure workflow.
- Audit retention is explicitly bounded to 90 days; safeguard summaries to 30 days. Receipts are bounded to 90 days and must cover the chosen backup/re-erasure window. No legal retention policy or provider deletion guarantee is asserted. Maintenance execution remains future work.
- Purge markers/receipts are worker assertions, not proof of physical deletion. Independent object reconciliation, secure temporary-file cleanup, five-minute sweeps, 15-minute deletion target, deletion-health admission checks and restore/re-erasure drills are still required before any upload route is enabled.
- Downgrade removes only new objects; it refuses while unpurged inventory or unexpired receipts exist. Once safe, it necessarily discards the new metadata. It is not a data-preserving rollback of Phase 2 records. Migration-owner inspection temporarily removes FORCE RLS inside the migration transaction so inventory cannot be hidden from the downgrade guard; failure rolls this back.

## API boundary for later chunks

Keep `/health`, `/api/v1/health` and `/api/v1/auth/*`. Existing `/sessions/*` PKCE contracts describe future OAuth only. Planned `/api/v1/uploads` and content/complete/preview/delete operations remain absent (404) in this chunk. Later integration tests may enable them only in a test-specific application configuration with controlled synthetic fixtures; a request flag cannot enable uploads.

The existing proposed upload contract is retained: authenticated ownership, five-minute hashed single-use ticket, bounded stream, immutable completion, authenticated no-store preview and asynchronous deletion. Future API validation must reject unknown fields, derive owners server-side, enforce quotas/consent and prevent client-controlled object keys/verification markers. These are deliberately not claimed as implemented by SQL.

## Source check

PostgreSQL official documentation reviewed 2026-09-25: [row security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html) and [constraints](https://www.postgresql.org/docs/current/ddl-constraints.html). Privileges and RLS are distinct; owners/BYPASSRLS require special care; cross-row invariants need more than CHECK constraints. Validation uses a real PostgreSQL instance, not SQLite or mocked SQL.

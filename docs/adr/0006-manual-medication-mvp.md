# ADR 0006: Phase 3A online manual medication management

Date: 2026-10-05. User-approved scope. Implementation validation is recorded in
[PHASE_3A_REPORT.md](../PHASE_3A_REPORT.md). This is not approval for a public release.

## Boundary

Android and Web share the existing Flutter/Riverpod/go_router app and FastAPI backend.
Reuse email/password authentication, native bearer verification, browser HttpOnly cookies,
Origin/CSRF checks and local revocation. Do not enable AI, OCR, prescription conversion,
medicine sources, normal-app uploads, OAuth, notifications, offline queues or deployment.
There are no seeded medicines or clinical claims. All test data is synthetic.

Manual names, strength, dose, route and instructions are independent literal user fields.
Manual identity is always unverified. Required dose text is not parsed into quantities or
converted to tablets. Source/product/analysis/confirmation/origin overrides are rejected.
Existing prescription-origin rows cannot be activated or relabeled through these APIs.

## Schedule and history semantics

Support daily explicit clock times, selected weekdays (Monday=0), fixed elapsed-hour
intervals from an explicit offset-aware anchor, and one-time offset-aware instants.
Dates are inclusive in the selected IANA timezone. End date or explicit open-ended choice
is required. No times, intervals or indefinite duration are inferred from instruction text.

The server uses the uv.lock-pinned CPython tzdata package through ZoneInfo.from_file,
independent of host timezone data. Python's official documentation recommends the first-party
tzdata package for Windows portability and documents explicit data sources:
https://docs.python.org/3/library/zoneinfo.html (checked 2026-10-05).
Timezone-data upgrades require the schedule regression suite and review of future schedules.
Existing occurrence instants and instruction snapshots are not rewritten.

DST gaps advance to the first valid local minute; overlaps choose the first instant only.
Coincident instants are deduplicated. Preview shows the actual upcoming instants and policy.
Activation verifies an owner/medication/version/input-bound HMAC preview, expiring after ten
minutes. It regenerates occurrences, retires the old schedule and cancels future pending
occurrences atomically. It never creates past doses before its effective activation time.
Edits retain immutable instruction revisions and suspend the old future schedule until
the user activates a new preview. A failed preview leaves a saved but inactive medication.

Generation is bounded to 90 days per call. Initial activation generates 90 schedule days.
POST /occurrences/materialize repairs/extends selected ranges on demand; GETs do not write.
No background reminder worker or outbox is introduced because this slice has no asynchronous
notification side effects. Retired revisions generate only instants before retirement;
deleted records cannot generate new occurrences. Unique schedule/instant keys prevent duplicates.
Limits: 100 active medications, 12 clock times per day, interval 1–8760 hours with at most
two decimal places, schedule dates 2020–2100; materialization is limited to ten years back
and two years ahead of the current date. These are application capacity limits, not advice.

Today/history currently display Asia/Kolkata day boundaries, explicitly labeled. Schedule
timezones remain as entered; travel never silently changes the regimen. Timestamp displays
retain their timezone/offset. The client has no independent scheduling engine.

Taken/skipped are user reports, never inferred from time or delivery. Pending past doses
remain unrecorded. Actions before the planned instant and actions on removed/cancelled
records are rejected. Corrections identify the latest event and append a replacement state;
they never overwrite an event. Occurrence versions determine correction order, independently
of client clocks and transaction start timestamps. Historical snapshots survive edits.

## Ownership, races, retries and privacy

Migration 0005_manual_medications follows 0004_upload_runtime; filename is
0005_manual_medication_management.py. Existing migrations and table names are preserved.
New columns are nullable for legacy rows. No migration activates schedules or fabricates
legacy review data. Downgrade refuses to discard populated new revision/idempotency tables.

Owner-consistent foreign keys, FORCE RLS and non-owner runtime grants protect data. The API
serializes per-user domain transactions and takes the same session advisory lock as logout
before checking revocation again. Consequently a mutation preceding logout can commit;
one ordered after revocation cannot. There is no promise to undo already committed writes.

Domain POSTs require UUID Idempotency-Key; replay is scoped by owner and operation. Responses
are encrypted with a separate MEDLM_MEDICATION_ENCRYPTION_KEY and expire after 24 hours.
Changed input using the same key returns 409. Event UUIDs additionally deduplicate beyond
that window. PATCH uses the complete allowed manual-field shape plus If-Match; DELETE also
requires If-Match except replay of an already removed owned record. Stale edits return 412.

Removal cancels future pending occurrences and retains history by default. Explicit
erase_history=true cascades the medication, instruction/schedule/occurrence/event records.
Both paths erase associated encrypted replay bodies and leave minimal invalidated request
tombstones until their original expiry, preventing replay from recreating removed data.
This is active-database erasure, not a claim of immediate backup or device erasure.
DELETE retries for a physically erased record return 204 while an owned unexpired request
tombstone proves the earlier removal; after that evidence expires they return 404.
Future deployment must define backup retention and restore/re-erasure before real-user launch.

The separate medication_maintenance command/role can read/delete only expired idempotency
rows. No scheduler is installed. Production must schedule it and monitor expiry; opportunistic
owner-scoped cleanup also occurs on POST. Key rotation must retain access to unexpired
responses or deliberately fail closed until they expire; do not silently replay a mutation.

Flutter stores medication state in memory only. Session transitions dispose owner-scoped
controllers and forms; late results are ignored. 401 clears the personal UI. Outages remain
visible, and failed actions are never marked successful. A failed PATCH with uncertain
commit status requires reload rather than blind resubmission. POST retries retain keys.
No medical request/response text, user fields or credentials enter logs or error messages.

## Validation and release limits

Local tests use real PostgreSQL with runtime roles and synthetic authentication adapters.
Flutter tests cover adapters/controllers, partial save recovery, owner/session transitions,
navigation, localization, keyboard/semantics and 200% text. Run all Phase 1/2 regressions.
Generate OpenAPI and the small response DTO bindings reproducibly; unsupported generation
schema shapes fail explicitly. The existing HTTP/auth transport is retained.

Live Supabase, physical-device TalkBack, real browser assistive technology, human Hindi/Telugu
review, iOS/desktop, public deployment, backups and regulatory/privacy review remain separate
release gates. No OpenAI/medicine-source/storage account is required for local Phase 3A tests.

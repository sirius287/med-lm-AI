# MedLM AI API specification

> Phase 1 implementation update (2026-09-24): the foundation is now implemented. See [PHASE_1_REPORT.md](PHASE_1_REPORT.md), [current API contract](contracts/openapi.json) and [scope decisions](docs/adr/0001-phase-one-boundaries.md). The remaining design below describes future behavior, not implemented clinical functionality.

Status: target design contract v1; contracts/openapi.json is the generated subset implemented in Phase 1. Date: 2026-09-24. Base `/api/v1`; JSON UTF-8 except direct binary uploads. OpenAPI will be generated from Pydantic contracts during implementation and checked against this document.

## Transport and authorization

Phase 2 Chunk 2 preserves the implemented email/password routes and success shapes. Hardened session semantics (mixed credentials 400, expired sessions 401/cookie removal, repeatable CSRF-protected logout, 429 with Retry-After, fail-closed outages) are documented in [ADR 0003](docs/adr/0003-auth-session-hardening.md). No upload or OAuth route is enabled.

HTTPS only. Native clients supply Supabase bearer JWT; browser uses same-origin opaque session cookie with CSRF header for mutations. Validate issuer, audience, expiry and signature through cached JWKS. User identity always comes from validated auth, never a body `user_id`. Every resource lookup is owner-scoped; cross-owner resources return 404. `/health/live` is unauthenticated and contains no dependency details; private readiness/metrics require operational access.

UUID resource IDs; ISO 8601 UTC timestamps, ISO dates, IANA timezone IDs, ISO country code (`IN` at launch), BCP 47 locale. Quantities use decimal strings plus explicit units, never binary float conversions. Nullable fields are explicit. Unknown keys rejected on writes. List endpoints use opaque cursor, default 25 and maximum 100 items, with `{items,next_cursor}`. Responses carrying personal data set `Cache-Control: no-store`.

Authenticated domain POST mutations require `Idempotency-Key` (random UUID); action uniqueness is additionally enforced in the database. Store owner+route+key+request hash for 24 hours. Same key/body replays original resource result; changed body yields 409. Do not persist/replay credentials or upload capabilities: reissue only after fresh authorization and within the original upload expiry. Authentication exchanges use single-use state/PKCE rather than domain idempotency. A resource's `version` becomes its ETag; PATCH, DELETE of versioned resources and confirmation require `If-Match`; stale versions return 412, missing precondition 428. DELETE replay on an already deleted owned resource returns 204.

Error body: `{error:{code,message,field_errors:[{path,code}],retryable},request_id}`. Do not echo medical text. Codes: 400 malformed, 401 auth, 403 prohibited action/CSRF, 404 unavailable resource, 409 workflow conflict, 410 expired upload, 412 stale version, 413 size, 415 media type, 422 semantic validation, 428 precondition, 429 quota, 503 provider/service unavailable. 429/503 include Retry-After when appropriate.

## Endpoints

Paths below are relative to `/api/v1`; all require an authenticated user except health, the state/PKCE-protected login bootstrap and the narrowly scoped erasure-receipt endpoint. POST creates normally return 201, asynchronous operations 202 with Location, GET/PATCH 200, DELETE 204 unless stated.

| Method / path | Request | Result and invariants |
| --- | --- | --- |
| POST `/sessions/web/start` | allowlisted login provider and return path | Unauthenticated bootstrap with Origin validation/rate limit; server stores PKCE verifier and expiring state tied to secure pre-auth cookie; returns authorization URL |
| POST `/sessions/web` | Authorization-code exchange with state/PKCE handled server-side | 200 session cookie and CSRF token; never accept an arbitrary user identifier |
| GET `/sessions/current` | none | Session/CSRF bootstrap after reload; server refreshes upstream tokens under a per-session lock, never returns them to web JavaScript |
| DELETE `/sessions/current` | CSRF on web | Revoke app session, unregister current push target; client clears caches/notifications |
| GET, PATCH `/me` | PATCH locale, timezone, notification privacy preferences | Profile/version; not a way to change auth identity |
| GET `/capabilities` | optional country and locale | Versioned market policy, enabled analysis/report capabilities, source coverage limits and supported locales; IN initially enabled, ISO country codes extensible |
| POST `/uploads` | content_type, byte_size, document_kind, consent_version, retain_for_review | 201 owned upload_id, gateway upload_url, single-use ticket, upload_expires_at, purge_at; no provider upload token |
| PUT `/uploads/{id}/content` | binary stream plus application ticket and user auth | Enforce ticket expiry, owner, size, timeout and single acceptance; 204 or safe error; repeated identical completed transfer may return prior acknowledgment, never overwrite bytes |
| POST `/uploads/{id}/complete` | checksum_sha256 | Validates stored bytes/type/limits, returns accepted metadata; checksum alone does not prove safety |
| DELETE `/uploads/{id}` | none | 202 deletion job, revokes review access and cancels dependent unfinished analysis |
| GET `/uploads/{id}/preview` | none | Authenticated gateway streams review bytes with no-store only before purge; 410 after expiry; rechecks revocation on every request |
| POST `/analyses` | upload_ids, kind: medicine/prescription, country: ISO code, locale | 202 job ID/state; IN initially enabled by policy; uploads must be complete, owned and unexpired |
| GET `/analyses/{id}` | none | Stage, result IDs, safe failure/needs-input reason, verification_status when available |
| GET `/analyses/{id}/identity-review` | none | Versioned observations/candidate set, uncertainty reasons, required fields and prior decisions; no default candidate selection |
| POST `/analyses/{id}/identity-reviews` | If-Match candidate-set version; decision: select/correct/reject, candidate_id nullable, reviewed identity fields | 201 immutable review with linked reanalysis_job_id when selected/corrected; explicit user decision required before candidate attachment; evidence verification runs again |
| POST `/analyses/{id}/cancel` | none | 202; cancellation fencing prevents late worker publication |
| GET `/reports`, `/reports/{id}` | optional cursor | Evidence-bearing report; no implied personalized dose advice |
| POST `/reports/{id}/reverify` | none | 202 job; successful refresh creates new immutable revision |
| DELETE `/reports/{id}` | If-Match | Delete personal report content and derived explanation; shared public sources remain |
| GET `/prescriptions`, `/prescriptions/{id}` | optional cursor | Draft version, line items, review flags, preview availability |
| PATCH `/prescriptions/{id}` | expected full line edits keyed by line ID | New draft revision; invalidates pending confirmation of superseded draft |
| POST `/prescriptions/{id}/confirmations` | draft_version, per-line reviewed fields, included/excluded state | 201 immutable confirmation; validates full field review and records corrections |
| POST `/prescriptions/{id}/medications` | confirmation_id, selected line_ids, explicit schedule inputs | Atomic creation; confirmation must match current draft, all selected lines reviewed; no activation from extraction alone |
| DELETE `/prescriptions/{id}` | If-Match | Erases draft/confirmation text; existing medications retain user-selected data with source link removed; explain scope in UI |
| POST `/medications` | manual-entry identity, dose instructions, optional source_report_id | 201 user-entered medication; report dose information cannot auto-populate a personal regimen |
| GET `/medications`, `/medications/{id}` | active filter/cursor | Medication and current schedule reference |
| PATCH `/medications/{id}` | allowed user edits | Increment version; instruction changes suspend future scheduling until updated preview/activation |
| DELETE `/medications/{id}` | If-Match; optional `erase_history=true` | Tombstone and cancel future occurrences; purge personal history if requested |
| POST `/medications/{id}/schedules/preview` | ScheduleInput | 200 normalized proposal and next 10 occurrences; no schedule side effects |
| POST `/medications/{id}/schedules` | ScheduleInput, acknowledged preview hash, medication_version | 201 immutable active revision, retiring prior schedule transactionally |
| GET `/occurrences` | from/to (max 90 days), medication_id, cursor | Due/recorded occurrence state and version; no implicit skipped state |
| POST `/occurrences/{id}/events` | event_id, type, expected_version, client_at, optional snooze_until | 201 event and updated occurrence; atomic conflict check, retries deduplicated |
| POST `/medications/{id}/unscheduled-doses` | event_id, taken_at, user-entered dose_text, optional note and supersedes_id | 201 user-reported PRN/unscheduled dose record; no schedule, recommendation, skipped or snoozed state; deduplicate event_id; correction must reference an owned prior record |
| GET `/history` | from/to, medication_id, cursor | User-reported dose events including corrections |
| POST `/devices` | installation_id, platform, capabilities, push token/subscription | Upsert owned device; token encrypted, omitted from responses |
| PATCH `/devices/{id}` | permission/capability state, is_primary, timezone | One primary reminder device per user; server does not trust capability claims as authorization |
| POST `/devices/{id}/schedule-acks` | schedule_version, occurrence_ids, scheduled_through, failures | Tracks local scheduling health, not proof of delivery |
| DELETE `/devices/{id}` | none | Revoke token and routing; device locally cancels notifications |
| GET `/sync` | opaque cursor | Changes/tombstones including occurrence revisions; expired cursor returns 409 sync_reset_required |
| POST `/exports` | format: json, recent reauthentication proof | 202 export job, short-lived authenticated download; no deleted images included |
| GET `/exports/{id}` | none | Job state and expiring download ticket when ready |
| DELETE `/me` | recent reauthentication token | 202 account-erasure operation; disable sessions/jobs immediately |
| GET `/privacy-operations/{id}` | none | Owner-scoped deletion state while authenticated |
| GET `/erasure-receipts/{id}` | Authorization: Receipt opaque_status_token | Minimal account-erasure status after session revocation; token hash stored server-side, expires after 30 days, no personal data or mutation access |

## Core data shapes

`ExtractionField = {raw_text:string|null, normalized_value:typed|null, unit:string|null, image_id:uuid|null, bounding_box:[x,y,w,h]|null, alternatives:[], ambiguity_reason:string|null, review_status:unreviewed|confirmed|corrected|unresolved}`. Coordinates are normalized 0..1. A null image link after deletion does not remove the recorded transcription provenance.

`PrescriptionLine = {id, medicine, strength, dose, frequency, route, duration, time, food_instruction, special_instruction, identity_status, candidate_ids}`. Each named field is an ExtractionField. Confirming a missing field records that it was absent; it does not invent a value. Critical missing schedule fields still block activation. Excluded/unresolved lines are never converted silently.

`Report = {id,version,analysis_id,country,locale,verification_status,product_id|null,fields,evidence,verified_at|null,source_checked_at,stale_after,pipeline_version,limitations}`. `fields` contains every key in REQUIREMENTS. A field uses `{status,value,claim_ids,evidence_ids}`. `Evidence = {id,provider,external_id,version,country,locale,url,section,excerpt|null,content_hash,source_updated_at,retrieved_at,verified_at}`. Provider-controlled URLs are allowlisted on ingestion. `verified_at` stays null when no verified match exists.

`ManualMedicationInput = {display_name,product_id|null,strength_text|null,dose_text,route_text|null,instructions|null,origin:manual}`. Required personal dose text is user-entered; manual unverified identity is permitted and clearly marked. API rejects attempts to set server-controlled verification status or confirmation identity.

For scanned input, include `analysis_id` and `identity_review_id` when required. Server-derived origin/provenance cannot be overwritten by `origin:manual`: any submitted analysis/report/product link must satisfy its identity-review gate. A genuinely independent manual record is allowed but is never tagged scan-verified. Identity review stores `{id,analysis_id,candidate_set_version,decision,selected_candidate_id,reviewed_fields,confirmed_at}`; a correction supersedes the candidate set and requires a new review if matching remains uncertain. Prescription lines refer to the same review mechanism when product identity is ambiguous.

`ScheduleInput = {kind:daily_times|weekdays|fixed_interval|one_time,local_times:[],weekdays:[],interval_hours:null|decimal,anchor_at:null|timestamp,one_time_at:null|timestamp,time_zone,start_date,end_date|null,dose_text,time_basis:wall_clock|elapsed,dst_gap:next_valid,dst_overlap:first,food_instruction|null,origin:manual|confirmed_prescription,confirmation_id|null,line_id|null}`. Types are a discriminated union: reject incompatible combinations. Start/end dates inclusive in schedule timezone; UTC instants are stored per generated occurrence. Open-ended schedules require explicit user choice. Do not infer indefinite duration from missing prescription duration.

Schedule preview returns `{proposal_hash,expires_at,medication_version,confirmation_id,occurrences:[{planned_at,local_display}],warnings}`. Activation recomputes the hash and validation; a preview is not authorization. Reminder timing preferences have a distinct origin from prescribed instructions. Confirmed-prescription creation can store medications without schedules when required timing remains unresolved.

At every schedule activation, the server derives origin from the medication and checks dose/route/frequency/duration/food fields against its confirmed instruction revision. Reject inconsistent fields with 422 `instruction_mismatch`; a caller-provided manual origin does not bypass this check. Changes to clinical instructions from a prescription return through draft edit/reconfirmation. If the source prescription was erased, creating a changed regimen requires a fresh, explicitly reviewed user-entered instruction record, without recreating erased source data. Already active schedules remain bound to their minimal confirmed snapshot.

That post-erasure review is submitted through medication PATCH as `instruction_review:{base_version,fields,reviewed_fields}` after the UI displays all proposed values. The server validates full review, writes an immutable instruction snapshot with actor/time/origin and suspends the old future schedule until activation. A single unchecked `confirmed` flag is insufficient. In-app review records user intent, not correctness of independently entered clinical instructions.

`DoseEventInput = {event_id,type:taken|skipped|snoozed|corrected,expected_version,client_at,snooze_until|null,supersedes_event_id|null,note|null}`. `recorded_at` is server-assigned; preserve client time as a separate field. Snooze is allowed only on a nonterminal occurrence, must be in the future and before the next regular occurrence/end boundary, and never creates an extra dose. Corrections append rather than overwrite events. Conflicting offline terminal actions return 409 with safe conflict metadata for explicit reconciliation.

## Workflow invariants

Uploads use random immutable storage keys and five-minute, single-use application gateway tickets. These are not Supabase signed upload URLs. Tickets are bound to authenticated user, upload and allowed size; completion pins object version/hash and rejects replacement. Review uses authenticated streaming, not a reusable bearer URL. No arbitrary remote-image URL input. Gateway/worker temporary files, processing copies and optional review copy share the same original expiry; retries never extend retention.

Confirmation captures user ID, draft version, line/field decisions and timestamp. Conversion locks draft/current version, verifies confirmation and creates all selected records plus outbox entries in one transaction. Unique `(confirmation_id,line_id)` prevents duplicate medication creation beyond the idempotency window. Later user changes to a medication do not mutate the original confirmation.

Analysis workers retry transient failures at most three attempts within job TTL, using a lease and fencing token. Client polling backs off; clients never poll OpenAI directly. New report versions require full evidence validation. No client endpoint accepts model-authored tool calls as privileged commands.

Offline actions synchronize individually through the events endpoint, then fetch `/sync`; reject stale/conflicting writes rather than last-write-wins for dose state. Schedule changes commit server-side before being considered active on secondary devices. The UI shows pending local edits and possible stale notifications until acknowledgments arrive.

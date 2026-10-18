# ADR 0007: Phase 3B synthetic analysis contracts

Date: 2026-10-06; lifecycle update 2026-10-07. Base: f064621. Chunks 1/2 committed
at edbadbc/abea49f. Chunk 3 is committed at 4775ed1; Chunk 4 at 97fa471.
Chunk 5 human review is committed at 4ac50ca (2026-10-11).
Chunk 6 report assembly is committed at 7b3d4eb (2026-10-15).
This ADR supersedes historical phase numbering, not
the safety, ownership or deletion invariants of ADRs 0002–0006.

## Approved boundary

Android/Web, online-only, one JPEG/PNG/WebP image per analysis. Controlled synthetic
fixtures cover strips, bottles, tubes, boxes/labels and prescriptions with multiple
lines. General file picking, camera capture, HEIC/PDF and multipage merging are
deferred. No clinical uploads, notifications, offline sync, deployment or iOS/desktop
completion claim. No fixture data is represented as a real medicine or medical fact.

Later chunks may implement an explicitly injected synthetic harness, fixture and
disabled-by-default Astra adapters, mandatory review and evidence-aware reports.
Credentials alone must not enable medical uploads. Live synthetic provider calls
need separate approval and a budget; no such call is part of Chunk 1.

Prescription conversion and automatic transfer of extracted dose/schedule fields
into medications are deferred. A later UI may link to existing manual entry without
prefilling clinical fields. Existing manual-management behavior remains unchanged.

## Contracts and trust boundaries

`analysis.py` defines observations, document structure, uncertainty, review,
synthetic provenance and the pure processing state machine. `analysis_contracts.py`
defines proposed harness request/response shapes; neither is registered as a route.
The existing OpenAPI artifacts still describe only implemented endpoints.

All models reject extra fields. Missing observed values are explicit nulls, not
omitted output. Literal text is preserved, including whitespace, units and decimals.
Normalized values are strings, never inferred numeric conversions. A normalized
value/unit requires observed text; this structural rule cannot establish factual
support. Later semantic validation must compare normalization against that text.
Strength and dose are distinct mandatory field containers with independently
nullable values. A missing dose cannot inherit strength. Coordinates are normalized
finite numbers, positive-area boxes wholly inside the image. Locations may be null.
Prescription lines retain unique IDs and ordinals; packaging cannot contain lines.
Empty prescription lines represent no extraction, never a successful acceptance.

Provider output contains no review/verification/provenance authority. Trusted server
assembly later attaches fixture identity/checksum and extraction revision metadata.
The checksum DTO is not proof of allowlisting: admission must validate actual bytes.
Confidence is nullable and explicitly uncalibrated, with provider/fixture origin.
No score triggers acceptance, verification or a claimed probability of correctness.

User review (`unreviewed`, `confirmed`, `corrected`, `unresolved`), verification
(`unverified`, `ambiguous`, `unsupported_market`) and synthetic provenance are
separate dimensions. This slice cannot represent supported clinical verification;
`verified_at` stays null. A user can confirm absent text without inventing it.
Corrections are separate from immutable observations and may explicitly clear a
value. Later services must authenticate reviewers, bind current revisions, validate
the complete expected field-key set and line dispositions, compare confirmed values,
and reject stale/foreign candidates. A structurally valid submission is not acceptance.
Chunk 1 introduced no confirmation endpoint or persistence. Chunk 2 adds storage
constraints only; field coverage/semantic acceptance and authenticated review
services are still later work, with no authentication bypass.

## Chunk 3 approved lifecycle decisions (2026-10-07)

Chunk 2 is committed at abea49f. Chunk 3 is now authorized, synthetic harness only.
Successful completion still atomically publishes an extraction revision; no HTTP
endpoint accepts observations or fabricates a result. Completion is exercised with
test-only observations through the persistence path. Actual extraction is unavailable.
Processing completion retains the review copy until review completion, cancellation
or its original deadline. Cancellation/expiry reuse the existing deletion queue;
processing completion does not queue whole-upload deletion. Expiry is a separate
durable parent marker, never a replacement processing state. It invalidates effective
leases and blocks progress/publication while leaving historical job state intact.
Queued jobs may now terminate in needs_input. No terminal job can reopen.

## State machine

Normal progression: queued → validating → extracting → retrieving → validating_output
→ completed. Every nonterminal state can fail, cancel or end in needs_input.
Completed, needs_input, failed and cancelled are terminal.
No stage skipping, reopening or same-state transition; Chunk 3 reuses encrypted
domain idempotency for request replay. Re-extraction creates a new job/revision.
Completed means processing ended, never that identity or medical facts were verified.
The pure transition helper does not supply persistence locking or worker fencing.

Cancellation stops publication/work; deletion also erases requested saved content.
Later workers must recheck session/account state, leases, cancellation and expiry
before publication and must not hold database transactions during network calls.

## Retention and report constraints for later chunks

### Stable analysis, attempts and revisions (approved for Chunk 2)

One `medicine_analyses` row is the stable workflow. Re-extraction never replaces
that parent. Each attempt has a new numbered `analysis_jobs` row; the state machine
above applies to each job, whose terminal state cannot reopen. Successful attempts
publish numbered, immutable extraction revisions. The parent retains explicit
current-job and current-revision pointers with optimistic version checks and row
locking. Starting another job does not erase the previous extraction, but reviews
are blocked until the current job has published its own revision. A stale job
cannot publish; a stale review cannot accept or mutate a newer revision.
The legacy parent `state` field remains unchanged for compatibility; current
attempt status is read from the current job, and cancellation from the parent.

Candidate sets, candidates and reviews bind the owner, stable analysis and exact
extraction revision. Prescription drafts link existing prescription parents to the
stable analysis; immutable prescription revisions, lines and confirmations bind
the exact extraction revision. Existing legacy prescription fields are preserved.
Review/correction records never mutate observations, and job completion never
changes verification or synthetic provenance into medical evidence.

Cancellation is irreversible on the stable workflow. Aggregate erasure may remove
immutable history; immutability prohibits edits, not authorized erasure. Deleting
analysis metadata must not delete upload inventory or bypass its deletion jobs.
Upload-link removal on eventual upload metadata erasure leaves saved text history
intact. Chunk 3 adds authenticated lifecycle routes and existing deletion-queue
integration. Extraction execution and complete review-field validation remain later work.

Existing non-review upload completion still queues deletion immediately. Synthetic
analysis requires explicit retain_for_review=true rather than changing this
behavior. Review copies expire at review completion/cancellation or the original
deadline (never later than 24 hours). Retries never extend it. All three independent
deletion safeguards remain required. Saved text/reports have separate disclosed
retention until user deletion; image deletion is not automatically text deletion.

Reports must retain all required field keys and explicit unavailable/conflicting
states. No Indian source access or licensing is assumed. Test evidence is marked
synthetic, never authoritative. No real verification, AI clinical explanation,
clinical translation or interaction-clearance claim is enabled in this phase.

## Sequence and acceptance

1. Typed contracts, pure state machine, documentation and focused tests (committed edbadbc).
2. Additive schema and least-privilege access (committed abea49f).
3. Synthetic upload/job lifecycle (committed 4775ed1).
4. Extraction adapters and semantic validation (committed 97fa471).
5. Versioned mandatory review (committed 4ac50ca).
6. Evidence-gated report assembly (committed 7b3d4eb).
7. Fixture-only Flutter workflow and full regression validation (implemented/validated
   locally 2026-10-15; uncommitted and awaiting review).

Chunk 7 uses explicit Flutter dependency injection and automated tests, with no new
authentication bootstrap/bypass or normal-app route. Bundle a generated catalog from
registered server synthetic fixtures, including supported empty/ambiguous variants.
Client descriptors are descriptive, not admission authority or medical evidence.
No fixture-download API, camera/picker, automatic medication transfer, provider calls,
new migrations/grants or deployment. Interactive cross-platform backend authentication
validation requires a separate decision. Historical audit/test records remain unchanged.

The workflow's service/controller/provider layer, fixture selection, observation,
review and report widgets live only under `apps/medlm/lib/analysis`. They are mounted
through explicit service injection, not app routing. All packaging fields and all nine
fields per prescription line are covered; line dispositions preserve original identities.
Corrections and final receipts stay separate from original observations and verification.
All 24 report information fields are shown as unavailable because no source was checked.
Generated catalog identity is descriptive; actual admission and dual-hash checks remain
server responsibilities. The catalog contains the five registered document kinds plus
empty/ambiguous box and prescription variants. No arbitrary client fixture registration.

Chunk 1 acceptance: invalid/extra fields, null handling, coordinates, distinct
strength/dose, uncalibrated confidence, independent states and invalid transitions
have focused tests; existing foundation/contract tests pass; Ruff and whitespace
checks pass. No migrations, routes, Flutter changes, credentials or provider calls.
Passing these tests validates contract behavior, not OCR accuracy or medical safety.

Chunk 2 uses migration `0006_analysis_foundation` and an explicitly opt-in grant
script. Existing prescription parents are retained; `analysis_prescription_*`
tables are their revision-bound extension, not a separate prescription workflow.
Candidate sets and prescription lines assemble atomically and seal at transaction
end; observations, reviews and confirmations reject updates. Relational confirmation
lines bind the exact owner/analysis/draft/revision/line and confirmation, assemble
with their header, and reject partial line coverage at commit. This is persistence
integrity, not clinical acceptance or schedule authorization. Default runtime
grants, normal uploads, legacy tables/fields and migrations 0001–0005 are preserved.
Rollback refuses populated new metadata. Local database tests cover two-user RLS,
composite FKs, concurrency/staleness, replay, immutability and deletion behavior.
Chunk 2 supplied no worker, endpoint, provider, evidence or report functionality.

Chunk 3 adds migration `0007_analysis_lifecycle`: immutable original parent deadline,
separate durable expiry marker, session-bound per-job leases, fencing counters and
optimistic job versions. Null deadlines preserve legacy 0006 persistence but are never
admitted by the lifecycle API. Invoker-only guards require an accepted retained linked
upload and current lease before progression/publication. Lease acquisition rotates
token/counter, increments version and is capped at 60 seconds/original expiry. It is
not a same-state processing transition. Terminal jobs cannot acquire another lease.
New sessions may create a new attempt, but cannot operate the prior session's job.

Stable cancellation freezes every attempt and queues deletion without rewriting past
job states. An explicit leased cancelled transition also cancels the parent. Failed
and needs_input jobs retain the review copy to allow review/retry until original expiry.
Expiry is durably marked on status/mutation access; deadline guards and independent
upload maintenance remain effective without such access. No new worker is implemented.
Opt-in column grants preserve default-denied normal-app access. Downgrade refuses new
lifecycle metadata; empty/legacy-only rollback restores 0006 without loss of history.
The API has no observation submission or completed target. Tests alone publish synthetic
observations through the existing atomic repository path. Review-end handling, fixture
adapters, reports and all Chunk 4+ functionality remain unimplemented.

## Chunk 4: controlled extraction (2026-10-08)

This section supersedes the earlier chunk checkpoints only for controlled synthetic
extraction. No real uploads, live providers, evidence, reports, review service/UI,
medication conversion or later chunks are enabled.

Fixture registration is an explicit in-memory catalog of labelled synthetic test
images and expected observations, never folder discovery or filename matching.
Descriptors bind fixture ID/revision (currently revision 1), document kind, original
MIME, original SHA-256, sanitized PNG SHA-256, observation schema version 1 and
`synthetic_test_not_medical` purpose. Duplicate identity/hash registrations are refused.
Original upload hashes remain enforced by existing byte allowlisting. Stored bytes
are rehashed immediately before execution and matched against both storage inventory
and the registered sanitized hash. Client requests contain no fixture/provider metadata.

The deterministic adapter returns the existing observation contract. Semantic checks
compare literal/normalized fields, nulls, line IDs/order and uncertainty against the
registered expected observations. Partial output may omit observations/lines or leave
normalization null; it cannot introduce unsupported non-null text or silently remove
registered ambiguity from observed text. Empty valid output is needs_input even when
the registered fixture contains text. Confidence never determines acceptance/rejection;
its structure remains validated and its value is retained without calibration claims.
Prescription test labels are not real prescriptions or dosage instructions; strength
and dose stay separate. No medication or review record is created.

An injected extraction service operates on an existing current queued job with a
valid lease. Preflight checks authenticate owner/session and bind the retained upload
before advancing validating -> extracting. The adapter runs without an open database
transaction. A fresh owner/session/lease/version/content check precedes publication.
Successful output advances retrieving -> validating_output -> completed atomically
with an immutable revision. Retrieving performs no evidence retrieval in this chunk.

Approved outcomes: disabled provider or invalid fixture binding returns a safe error
before any processing transition; adapter failure/malformed output ends in failed,
with only adapter_failure/invalid_output codes saved; valid output with no observed
text ends in needs_input with no_observations and no revision. Partial/ambiguous
observations publish unreviewed/unverified, with verified_at null. Stale, expired or
cancelled work cannot publish even a failure over existing history. Review images
retain the original deadline after completion; prior deletion safeguards are unchanged.

POST /analyses/{id}/jobs/{job_id}/extract exists only with explicit test-harness
injection, requires authentication/CSRF where applicable, Idempotency-Key and current
job version/token/fence. Completed request replay reuses encrypted domain idempotency.
Concurrent in-flight duplicates return conflict; interrupted execution needs a new
attempt rather than reopening a job. No background worker is added.

The provider-neutral interface returns observations only. Server-selected identity
is captured before execution. DisabledAstraAdapter has no transport, SDK, environment
lookup or credential field; enabled can only be false and model is unconfigured.
Neither credentials nor adapter failure can trigger provider fallback. Real model
selection/access and request translation remain unimplemented and unvalidated.

Migration file 0008_synthetic_extraction_metadata.py uses revision ID
0008_synthetic_extraction (within Alembic's existing 32-character limit). It reuses
fixture_id, fixture_sha256 (original), contract_version and provenance, adding only
fixture_revision, sanitized_sha256, provider_id, model_id and pipeline_version to
immutable revisions, plus bounded terminal safe_error_code on jobs. Existing rows
retain null new metadata. Owner/RLS/lease guards remain; metadata-bearing publication
must match the owned upload hashes. Downgrade refuses new metadata/error codes and
otherwise preserves legacy history. Only opt-in UPDATE(safe_error_code) is added.

## Chunk 5: approved human review (2026-10-11)

Backend-only, explicitly injected synthetic harness. POST review-context prepares an
empty, server-owned candidate set for the exact current completed extraction revision;
candidate_id is always null. No product candidate is fabricated. For prescriptions it
also creates immutable revision/line snapshots. A separate source_line_id retains the
extracted UUID; relational IDs remain unique across repeated fixtures/revisions/users.
GET review-context reads saved observations, expected keys and immutable review history.

Submission requires the exact revision, candidate set and analysis version, all five
packaging fields or all nine fields per prescription line, and a disposition for every
line. Confirmed values equal exact raw_text, including whitespace/null. Corrections,
including explicit null clearing, are stored separately; observations and uncertainty
remain unchanged. No confidence threshold participates in review.

Decisions are confirm/correct/reject/unresolved. Field statuses remain unchanged.
Intermediate unresolved submissions append history and consume a concurrency version,
but accept no values and create no prescription confirmation. Field-review progress
may be recorded without acceptance. Included prescription lines require complete
confirmed/corrected fields; excluded/unresolved lines remain represented without
accepted instructions. Final confirm/correct require completed selected fields;
correct requires at least one correction. Reject is a final review rejection, not
cancellation, diagnosis or verification. Reject/unresolved receipts have no accepted
values. Final prescription submissions create the existing immutable confirmation and
all line dispositions; none authorizes medication creation or clinical use.

Final review closes the workflow and atomically queues the existing deletion process
using its completed reason. It cannot reopen or start re-extraction. Pending review
retains its image only until the original deadline. Image deletion does not erase saved
text/history, and actual deletion receipts remain the responsibility of existing workers
and independent safeguards. User review never sets verified_at or changes verification.

Identical receipt replay is permitted after image deletion/expiry, with fresh session,
owner and exact current-revision checks; changed bodies and superseded revisions are
rejected. Existing encrypted domain idempotency is reused. The immutable review row
stores a canonical request hash and can reconstruct its original receipt after cache
expiry, without another write. Other final submissions conflict. No transaction spans
provider work and no provider is invoked. Human review uses any valid owner session,
not a completed job's released processing lease.

Migration 0009 adds only review metadata, source-line binding, uniqueness and invoker
guards. It preserves FORCE RLS, composite owner FKs and existing restricted grants.
Populated managed review/source-line rollback refuses safely; prior migrations and
legacy history remain intact. No report, evidence, lookup, UI, notification or later
chunk is implemented. Historical checkpoint sections above remain dated history.

## Chunk 6: on-demand synthetic report projection (2026-10-12)

Approved scope: backend-only, no report persistence or migrations. Explicit test injection
enables a GET for an exact current completed extraction revision, even before review.
Read one owner-authorized snapshot under the existing parent lock; no transaction spans
external work. Revision changes, erasure and review writes serialize with this read.

Keep original observations, immutable corrections/history, prescription line identities
and dispositions, observation ambiguity, synthetic provenance and medical information
separate. Only eligible final confirm/correct produces accepted transcription; rejected,
intermediate, malformed or stale review cannot become accepted values. All 24 required
medical keys remain explicit. The service has no source integration and emits unavailable
fields, null values and no_authoritative_source_checked. No source-check date is invented.
Pure server-test descriptors can demonstrate conflicting alternatives/references while
keeping the value null; no synthetic descriptor is authoritative or accepted from HTTP.
Fixture provenance never becomes evidence. Product ID and verified_at stay null and
verification stays unverified. No clinical translation or medical explanation is generated.

Cancellation prevents new work but does not erase saved text. Report reads follow existing
review saved-text access after cancellation, original expiry and image deletion, while
explicitly reporting image availability. They do not refresh, reopen or extend anything.
Analysis erasure removes access. Final-review image deletion remains independent and intact.
No Chunk 7, Flutter, provider, clinical upload, lookup or automatic medication functionality.

Audit hardening (2026-10-15) preserves these decisions: report input validation fails
safely without masking unrelated errors, and field/evidence conflicts plus observation
summaries must agree with their original inputs. Analysis text erasure includes owned
encrypted replay bodies; existing invalidated request markers retain their original expiry.
Verified upload inventory/receipts stay independent. No migration or security grant change.
Additional tests exercise saved-text reads after expiry/metadata removal and serialization
with erasure. Detailed findings and fresh validation are in
[the Chunk 6 engineering audit](../PHASE_3B_CHUNK_6_AUDIT.md).

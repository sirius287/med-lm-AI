# ADR 0007: Phase 3B synthetic analysis contracts

Date: 2026-10-06. Base: f064621. Chunk 1 committed at edbadbc; Chunk 2 persistence
is authorized, including the stable-analysis decision below. This ADR supersedes historical phase numbering, not
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

## State machine

Normal progression: queued → validating → extracting → retrieving → validating_output
→ completed. Every nonterminal state can fail or cancel; validating and later stages
can end in needs_input. Completed, needs_input, failed and cancelled are terminal.
No stage skipping, reopening or same-state transition; idempotent request replay is
a future service responsibility. Re-extraction creates a new job/revision.
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
intact. Lifecycle execution, automatic cleanup, complete review-field validation
and routes remain later chunks; this chunk supplies constraints and persistence only.

Existing non-review upload completion still queues deletion immediately. Synthetic
analysis will require explicit retain_for_review=true rather than changing this
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
2. Additive schema and least-privilege access (implemented locally; not committed).
3. Synthetic upload/job lifecycle (not started).
4. Extraction adapters and semantic validation (not started).
5. Versioned mandatory review (not started).
6. Evidence-gated report assembly (not started).
7. Fixture-only Flutter workflow and full regression validation (not started).

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
No worker, endpoint, provider, evidence or report functionality is supplied.

# MedLM AI development plan

> Phase 1 implementation update (2026-09-24): the foundation is now implemented. See [PHASE_1_REPORT.md](PHASE_1_REPORT.md), [current API contract](contracts/openapi.json) and [scope decisions](docs/adr/0001-phase-one-boundaries.md). The remaining design below describes future behavior, not implemented clinical functionality.

Status: Phase 1 foundation implemented under the subsequent explicit user request. Date: 2026-09-24. India-first launch confirmed. The original sequence below is historical; ADR 0001 defines the revised Phase 1 scope and Phase 2 recommendation. Do not start Phase 2 without authorization.

## Phase 0 — Architecture and research (this delivery)

Deliver the seven design documents and root AGENTS.md, inspect existing repository/tooling, verify official source capabilities, and record limits. Completion check: all eight documents exist, links/contracts are internally consistent, India-first scope is explicit, and no executable application files have been introduced. Unresolved procurement/legal decisions are documented; their existence does not prevent completing this planning phase.

## Phase 1 — Resolve launch dependencies and validate foundations

- Inventory/fix Flutter doctor, Android SDK/licenses/JDK, Python/uv and Windows build tooling; provision macOS CI and physical-device testing later. Pin SDK/dependency versions only after compatibility validation. Current local Flutter metadata is older than the official docs researched.
- Obtain Indian medicine catalog and authoritative label access. Evaluate vendors on Indian brands, combination formulations, manufacturer/marketer distinction, release forms, identifiers, local prescription status, coverage freshness and clinical editorial process. Require API/ingestion rights, citations, translations, caching, third-party LLM processing, derived explanations and user-facing redistribution terms.
- MIMS has a public developer portal, but the fetched page is branded for Australia; it does not establish India API coverage or licensing. Treat MIMS/CIMS and DrugBank as procurement candidates, not selected Indian data providers. [MIMS developer portal](https://developer.mims.com/), [DrugBank clinical API](https://docs.drugbank.com/v1/).
- Settle launch age scope, English/Hindi/Telugu review resources, hosting/processing regions, cost budget and privacy/regulatory assessments. Freeze product claims and source-coverage matrix.
- Verify actual `gpt-6-astra` access using synthetic data, strict output schemas, retention settings and rate limits. No real prescriptions before processor review.
- Spike notifications, secure local storage, image capture/HEIC conversion, web authentication and keyboard/screen-reader support across five platforms. Validate plugin maintenance/licenses and native gaps before committing to packages.
- Implement isolated feasibility prototypes only after Phase 1 is explicitly requested: a synthetic Astra image/schema call with refusal handling; the shared Flutter shell calling the same test backend on Android/iOS/web; the upload gateway's size/expiry/cancellation checks; and device notification scheduling/refill. Exercise Telugu recognition separately from UI localization. Keep prototypes separate from production clinical flows.
- Validate market-policy/provider contracts using IN and disabled US fixtures; verify that adding a market does not change client/reminder code. Prove uncertain-identity and prescription-confirmation contracts cannot be bypassed, including schedule edits, before production feature implementation.

Exit: evidence of Indian coverage/rights or an explicit reduced release limited to manual management/unverified transcription; documented provider privacy choices; successful synthetic model test; feasible five-platform capability matrix. A verified Indian medicine report cannot ship without the source gate.

## Phase 2 — Secure skeleton and accessible design system

Create proposed production monorepo, Flutter shell, API, migrations, CI and independent workers after implementation is requested. Build auth/session isolation, native secure storage, web cookie/CSRF flow, private buckets and deletion pipeline. Establish light/dark tokens, restrained neumorphism, responsive navigation and English/Hindi/Telugu localization scaffolding. Promote Phase 1 prototypes only after review.

Exit: all target client builds compile; two-user RLS/IDOR tests pass; synthetic image expiry/delete race tests pass; web keyboard and native screen-reader paths work; no frontend secrets.

## Phase 3 — Manual medication management and reminders

Build manual medicines, schedule preview/activation, start/end dates, history, taken/skipped/snoozed/correction events, offline queue, sync, device capability status and cancellation. This delivers useful functionality independently of AI/source availability.

Exit: property-based schedule tests cover DST, elapsed intervals, leap days, month/year boundaries and travel; duplicates/conflicts cannot silently corrupt history. Physical-device matrix covers permission denial/revocation, reboot, app termination, battery restrictions, clock change, notification actions and offline use. Windows/macOS packaging and browser closed-tab behavior verified. No promise of guaranteed reminder delivery.

## Phase 4 — Capture, extraction and prescription review

Implement transient upload processing, Astra vision schema, optional OCR comparison, uncertainty display, versioned review/confirmation and conversion of confirmed lines. Use synthetic/consented evaluation samples; no automatic reminders from extracted text.

Exit: every identity/prescription confirmation bypass/stale revision test fails safely; ambiguous dose/unit/frequency stays unresolved; failed/expired images purge; all five capture/input classes pass representative tests; labels and instructions remain usable at large text sizes. Prescription-derived schedule edits cannot override confirmed clinical fields or bypass review by claiming manual origin.

## Phase 5 — Indian verification and sourced reports

Implement approved Indian source adapter, source-version catalog, ingredient/product matching, per-claim provenance, evidence-constrained explanation and reviewed translation. Add US-source adapters only as explicitly labeled supplementary evidence. Add a licensed interaction checker only if coverage and validation justify it; general label interaction sections remain available otherwise.

Exit: full report-field matrix handles supported/unavailable/conflicting evidence; ingredient-only results never appear product-verified; combination products and decimal errors pass release safety suite; stale/outage cases cannot acquire fresh verification badges. Clinical reviewers approve target-market/language evaluation thresholds and results.

## Phase 6 — Production hardening and controlled release

Benchmark APIs/workers, bound cost, run adversarial/security evaluations, penetration test, restore/deletion drills and accessibility review. Complete source/processor contracts, legal launch assessment, privacy copy, incident runbooks, monitoring and signed desktop/mobile packaging. Roll out to a limited consented cohort with source/model feature flags and safe rollback.

Exit: no known critical/high unresolved security or clinical-safety failures; operations owner can disable bad source/model output; image-purge and reminder-scheduling health alerts are exercised; five-platform end-to-end flows pass. Store distribution and OS requirements are rechecked against current official policies at release time.

## Phase 7 — Expansion

Additional languages beyond English/Hindi/Telugu, richer explicitly entered regimens, more source coverage and optional caregiver features each require separate scope, privacy and clinical evaluation. US coverage is the first planned country expansion through its own MarketPolicy and source adapters; later countries follow the same interface and independent identity/label/interaction gates. Do not extrapolate English or US-source accuracy to Hindi/Telugu handwriting or Indian brands.

## Test strategy and release evidence

| Area | Required evidence |
| --- | --- |
| Domain | Unit/property tests for schedules, state transitions, quantities and null handling |
| Database | Real PostgreSQL migration, RLS, transaction, duplicate-worker and erasure race tests |
| Contract | Generated OpenAPI/Dart schema parity; all API status/ownership/precondition cases |
| AI | Expert-labeled test sets; critical-field errors, false verification, abstention and unsupported claims by language/product type |
| Sources | Adapter contract fixtures with revision changes, withdrawn products, conflicting forms and provider outages |
| UX | Five-platform end-to-end workflows; English/Hindi/Telugu, font shaping, RTL-ready layout checks, themes, scaling and assistive technology |
| Notifications | Physical devices and supported browsers; permission changes, reboot/sleep, cancellation and duplicate delivery |
| Privacy/security | Secret scans, malicious uploads, prompt injection, SSRF, IDOR, deletion/restore and log-content inspections |
| Operations | Load/cost benchmark, worker recovery, provider throttling, backup restore and incident drill |

Define evaluation datasets, minimum sample sizes and acceptance bounds before tuning. Finite test success is not a guarantee of medical correctness. AI, schema, source, prompt or translation changes require the relevant regression suite before rollout. Ordinary documentation changes need link/consistency checks, not application test scaffolding.

## Major risks and decisions

| Risk | Mitigation / release consequence |
| --- | --- |
| Indian product/label coverage and licenses | Highest launch dependency; procure and audit coverage; abstain for unsupported products |
| Handwriting and look-alike drug names | Per-field uncertainty, conservative matching, mandatory review; no invented dose |
| Missing or stale clinical evidence | Versioned sources, 24h proposed refresh, explicit age/conflict status; no unsupported negative claims |
| Model access, drift, cost and latency | Synthetic access test, evaluations, controlled model config, quotas and per-job budgets |
| Cross-platform reminder reliability | Local scheduling and capability UI; tested adapters; no blanket delivery guarantee |
| Privacy leaks and processor retention | Minimal images, verified purge path, no body logs, processor contract gate |
| Incorrect schedule changes across devices | Immutable revisions, idempotent occurrence IDs, conflict review, cancellation acknowledgments |
| Neumorphism reduces accessibility | Decorative shadows only; measurable contrast, focus and target-size tests |
| India regulatory/privacy requirements | Review actual intended use, launch-date rules and data flows before public claims |
| Translation alters clinical meaning | Reviewed glossary, unit preservation, original text access and language-specific evaluations |
| Five-platform scope stretches delivery | Stage vertical slices; platform release gates remain mandatory; make capability differences explicit |

No trustworthy time/cost estimate is possible until data licensing, team capacity and platform spikes are known. Track source procurement, Apple build access and clinical review as critical-path dependencies rather than hiding them inside implementation estimates.

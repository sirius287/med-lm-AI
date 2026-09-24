# MedLM AI security and privacy design

> Phase 1 implementation update (2026-09-24): the foundation is now implemented. See [PHASE_1_REPORT.md](PHASE_1_REPORT.md), [current API contract](contracts/openapi.json) and [scope decisions](docs/adr/0001-phase-one-boundaries.md). The remaining design below describes future behavior, not implemented clinical functionality.

Status: proposed controls, not a security certification. India-first launch, research date 2026-09-24. All prescription images, extracted text, medication lists and dose history are treated as sensitive even when a statute uses different terminology.

## Trust boundaries and threats

| Threat | Required control | Verification |
| --- | --- | --- |
| Cross-user access / guessed IDs | Owner checks, composite owner FKs, database RLS, private storage | Two-user negative tests across every endpoint and worker pathway |
| Credential or refresh-token theft | TLS, short-lived JWT, native secure storage, web HttpOnly session, rotation and revocation | Expired/forged JWT, revoked session and CSRF tests |
| Malicious upload / decompression bomb | Magic-byte checks, decode/dimension/size limits, patched isolated codecs, re-encode, strict egress | Malformed and oversized image fixtures; resource-limit checks |
| Prompt injection in image/source text | Treat content as data; fixed schemas, no arbitrary model tools, allowlisted retrieval | Adversarial image/source evaluations cannot trigger writes or exfiltration |
| Medical hallucination or incorrect source match | Evidence gate, exact formulation checks, abstention, mandatory review | Critical-field and provenance release suite |
| Secret exposure in app/logs | Secret manager, log allowlist, CI secret scan; no model/provider service keys in client | Inspect release bundles and telemetry fixtures |
| Lost device / browser XSS | Minimal local data, native encryption, CSP, no medical HTML rendering, auto-lock option | Storage inspection, injection tests, logout wipe |
| Leaked push content | Generic lock-screen text; opaque IDs; no medicine names/doses in remote payload | Inspect provider payloads and notification previews |
| Duplicate actions / replay | Idempotency, unique event IDs, row locks, optimistic concurrency | Retry and conflicting offline-action tests |
| Worker completing after erasure | Tombstones, fencing tokens, cancellation checks, deletion reconciliation | Race tests with paused/resumed jobs |
| Insider access | Least privilege, MFA, audited just-in-time support access, no routine image browsing | Access review and support-tool audit |
| Denial of service / cost abuse | Per-user/IP quotas, bounded image/token budgets, worker concurrency limits | Load test and provider outage drills |

## Authentication and authorization

Supabase Auth is the identity provider. Use verified JWT signatures against configured issuer JWKS, exact audience and expiration checks; cache signing keys safely and refresh on rotation. Native clients keep refresh tokens in Keychain/Keystore or a vetted desktop credential vault. Browser auth uses same-origin FastAPI session exchange, PKCE/state, Secure/HttpOnly/SameSite cookies and CSRF tokens; browser JavaScript never holds long-lived refresh credentials. Restrict OAuth redirect allowlists. [Supabase JWT documentation](https://supabase.com/docs/guides/auth/jwts).

JWT signature validation alone does not make logout immediate. FastAPI checks disabled-account state and revoked `session_id` on every personal-data request; app logout records revocation before upstream sign-out. For sensitive actions also verify the upstream session remains valid through a narrow server-side check. Deny access if required revocation state cannot be checked. This is an application control rather than an assumption about stateless tokens. [Supabase session behavior](https://supabase.com/docs/guides/auth/sessions).

Web login bootstrap is intentionally unauthenticated but bound to a single-use server PKCE verifier/state and pre-auth cookie, with Origin checks, rate limits and allowlisted redirect/provider values. FastAPI handles callback/exchange and serialized refresh. Flutter Web calls the same domain API using the opaque cookie and never depends on direct Supabase client sessions, Storage or Realtime access. Store only a hash of the app session identifier; issue no access/refresh tokens in web API responses.

Use a non-owner database runtime role with no BYPASSRLS; transaction-local user context is set only from validated identity and reset by transaction completion. Storage upload tickets are issued only after ownership and quota checks. Supabase service-role keys bypass normal access restrictions and must be isolated to narrow operational components, never shipped or used for generic user API queries. [Storage access control](https://supabase.com/docs/guides/storage/security/access-control), [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security).

Require recent reauthentication for exports, account deletion and sensitive account changes. Administrators use MFA. No caregiver/shared-account access in the initial permission model. Rate limits do not replace authorization. CORS allows only known origins; cookie mutations also check Origin and CSRF. Apply CSP, HSTS, no-referrer on sensitive pages, upload isolation and dependency patching.

## Data lifecycle

| Data class | Proposed retention and handling |
| --- | --- |
| Original image, sanitized image, crops and OCR temporary files | Delete processing copies when processing ends; only a minimized review copy may remain with explicit retain_for_review choice until review ends, cancellation or 24h from upload; target <=15 minutes after trigger, no retry extends expiry |
| User image preview | Authenticated gateway stream with owner/revocation checks and no-store; never public or CDN-cached; unavailable after purge |
| User device image | Keep only while needed for capture/review; delete app-created temporary files on success/cancel/expiry; never delete the user's original photo-library asset |
| Extracted prescription text and saved reports | Retained for user's requested functionality until deletion/account erasure; clearly disclosed separately from image retention |
| Medication records and history | Retained until user deletion; medication removal preserves history unless user selects erase-history |
| Provider request/response bodies | Not logged in application/APM; no raw AI traces; provider retention must be disclosed separately |
| Idempotency responses | Encrypted, <=24h; exclude credentials and upload secrets |
| Exports | Private, authenticated/expiring access, <=24h then purge |
| Push tokens and subscriptions | Encrypted at rest; revoke on logout/device removal; prune invalid/inactive targets |
| Operational logs | Proposed 30 days, pseudonymous IDs, status and timing only |
| Security audit | Proposed 90 days, minimized, legal review before final policy |
| Database backups | Proposed maximum 30 days with provider support verified; reapply deletion ledger before restore opens |
| Public/licensed source cache | Independent of user retention; obey license TTL and redistribution restrictions |

These are proposed service policies, not existing guarantees. An expiry timestamp is insufficient: run a deletion worker at least every five minutes, independent reconciliation of object inventory and expired rows, alerts on lag, and an incident procedure when expiry is exceeded. Provision a provider lifecycle expiry or equivalent independent deletion path; if a storage product cannot satisfy the hard limit, use a suitable transient bucket provider. Exclude image objects from backups/versioning where possible; verify provider behavior contractually. Keep deletion receipts without image contents or identifying filenames.

Five-minute upload tickets are enforced at the authenticated application gateway and are single-use. Do not issue a longer-lived storage-provider token and claim that rejecting API completion revokes it. Stream with byte/time limits; secure gateway spool files and include them in purge reconciliation. Store accepted content under an immutable backend-only key, and prevent completion/cancellation races from recreating erased objects. Deny new uploads if the deletion subsystem cannot meet the stated policy.

Account erasure: disable account/session and all analysis/notification work immediately; purge live personal records, objects, tokens and exports with a proposed <=24h operational target. Backups age out within the disclosed backup window. Document any legally required minimal retention and notify the user; do not silently exempt every audit table from deletion. Revoke frontend caches on next contact; a disconnected device cannot be remotely wiped immediately, so local expiry, encryption and logout handling are essential.

Already scheduled notifications on a disconnected device cannot be cancelled remotely until that device runs/syncs. The finite scheduling horizon and generic local notification content bound this risk; expose pending cancellation status. Local logout always clears that device's pending notifications. Do not represent remote logout/erasure as an immediate OS-level wipe on offline devices.

## OpenAI and other processors

Set Responses `store:false`; use foreground provider calls inside our durable worker, avoiding provider-side conversation/file state where practical. This setting does not by itself provide Zero Data Retention: default abuse-monitoring retention and image safety exceptions are separate. ZDR and other controls require eligibility/configuration and endpoint/model review. Do not promise all providers erase images immediately. [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data).

Include prompt-cache retention and regional-processing behavior in that review; inline images and `store:false` do not by themselves establish zero retention or India-only processing. Do not log dynamic JSON schemas containing patient text. Account-specific processor settings remain a pre-production dependency.

Before sending real medical data, verify contracts, processing regions, subprocessors, incident terms and actual account retention. Make provider/data-flow disclosure part of consent. Do not enroll private medical data into training or evaluation without separate explicit permission. Use synthetic fixtures for initial connectivity tests. Optional OCR providers get a separate assessment; public medicine lookups receive only minimum product query fields, never patient identity or the complete prescription.

Medicine-data licensing must explicitly permit transmission to a third-party LLM, derived explanations, English/Hindi/Telugu translations, caching, excerpts, attribution and end-user redistribution. A clinical API subscription alone does not establish these rights. The evidence adapter must enforce entitlements before sending source text to Astra; when rights are absent, render only contract-permitted source content through reviewed templates or withhold it.

OpenAI, licensed medicine API, Supabase and notification credentials belong in server secret management. A Supabase publishable key and web VAPID public key are public identifiers, not substitutes for access controls. CI uses short-lived workload identity where supported, protected environments and restricted deployment roles. Rotate compromised credentials and invalidate affected sessions promptly.

## India-first privacy and regulatory gate

Review India's DPDP Act, notified rules and commencement schedule with qualified counsel for the intended launch date; document consent/notice, withdrawal, erasure, grievance handling, processor contracts, breach response, children/age controls and cross-border processing. No blanket India-only residency requirement or compliance claim is assumed in this design. The MeitY rules landing page was located but its text did not render in this research tool; verify the Gazette text and effective provisions before finalizing policy. [MeitY DPDP Rules resource](https://www.meity.gov.in/documents/act-and-policies/digital-personal-data-protection-rules-2025-gDOxUjMtQWa).

Select adult account holders for the first release as a proposed scope; pediatric information remains general source content, and does not imply child accounts or pediatric prescribing. Obtain review of actual functionality and marketing claims under India's medical-device framework. An informational disclaimer alone does not decide classification; CDSCO's framework includes software within relevant intended uses. [CDSCO medical-device information](https://www.cdsco.gov.in/opencms/opencms/en/Medical-Device-Diagnostics/Medical-Device-Diagnostics/).

Do not claim HIPAA/GDPR/DPDP compliance solely from selecting a hosting provider. US/EU launch and clinical integrations require their own legal, contractual and technical gates.

## Operational controls

Separate dev/staging/prod accounts, encryption keys, buckets and data. No production snapshots on developer laptops. Use TLS in transit, managed disk/database encryption, KMS-backed encryption for tokens/sensitive exports and protected local storage. Disable request-body logging in gateway, API, tracing and crash reporters. Never put medical text in URL query strings, analytics event properties or notification provider labels.

CI runs secret scanning, dependency/license checks, static analysis and security-critical tests. Maintain SBOMs and patch ownership. Before launch, commission penetration testing and a clinical-safety review. Incident runbooks cover data breach, leaked key, false identification, stale evidence, image purge failure and notification outage. Feature flags must disable AI publication or affected sources while preserving access to user medication records and local reminders. Recovery drills verify both restored service and restored deletion state.

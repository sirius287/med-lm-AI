# MedLM engineering preview release checklist

Audit started 2026-10-21; local validation completed 2026-10-22.
Starting commit: `b8b28b0`, branch `main`, clean tree.
Destination configured locally: `https://github.com/sirius287/med-lm-AI.git`.
This checklist does not authorize a visibility change or production deployment.

Progress is the number of **passed** criteria below divided by 20. Blocked, failed,
not-run and partially implemented criteria do not count. These are engineering
preview criteria, not clinical validation. Historical phase reports remain dated
evidence and do not substitute for fresh validation.

| ID | Release criterion | Status | Evidence / blocker |
| --- | --- | --- | --- |
| R01 | Actual feature inventory and unavailable medical capabilities documented | Passed | README inventory and visible localized preview limits |
| R02 | Safe configuration diagnostics and secret generation tested | Passed | Focused config tests plus real isolated setup smoke |
| R03 | Guarded local database initialization and migration tooling tested | Passed | New isolated cluster: non-superuser owner migration and restricted runtime login/grants |
| R04 | Real local runtime database provisioned and permissions verified | Passed | Owner ran the private initializer; actual `dev.py check --database` passed local runtime identity/grants/restrictions/FORCE RLS read-only |
| R05 | Real Supabase email confirmation, login and logout verified | Blocked | Configuration and authorized read-only Auth/JWKS checks pass; user reported registration/confirmation failure. Safe error/outcome diagnosis and full private browser journey remain required |
| R06 | Full backend suite passes on an isolated local PostgreSQL target | Passed | Corrective full run: 361 passed/0 failed/0 skipped; historical 350-test run retained in audit |
| R07 | Migration, ownership, RLS, grants and authentication concurrency regressions pass | Passed | Real PostgreSQL suite and separate owner/runtime setup smoke |
| R08 | Flutter unit/widget regression suite passes | Passed | Fresh 181 passed after preview copy correction |
| R09 | Flutter analysis passes | Passed | No issues |
| R10 | API/client/catalog and localization parity pass | Passed | All six generation/export checks, 197 en/hi/te keys; synthetic gates unchanged |
| R11 | Flutter production web build passes | Passed | Release JS build with self-hosted resources, 94.6s; Wasm not claimed |
| R12 | Android debug build passes | Passed | 33.0s; signing/device distribution remains separate |
| R13 | Local API/web smoke test returns expected JSON/401 and HTML boundaries | Passed | Actual TCP/static HTTP checks; browser runtime/live sign-in not verified |
| R14 | Secret scan, dependency review and Python lint/format checks pass | Passed | Current/history supplementary scan, manual diff, 33 Python and 102 hosted Pub versions clear of known advisories; Ruff passed |
| R15 | Reproducible backend/Flutter CI defined and locally checked | Passed | Immutable actions, pinned SDKs, static YAML/security and Compose checks; local command equivalents passed |
| R16 | CI executes successfully on intended GitHub repository | Passed | [Corrective hosted run](https://github.com/sirius287/med-lm-AI/actions/runs/39712515755) on 1429309: 361 backend tests, 181 Flutter tests, analysis, parity/audits, Web and Android builds passed |
| R17 | First-time setup, contribution, disclosure and release documentation complete | Passed | Authoritative Windows/README/contribution/disclosure guides and owner-approved MIT source license; dependency/data licenses remain separate |
| R18 | Same-origin HTTPS deployment configuration prepared and checked | In progress | Static config/Compose checks passed; Docker daemon stopped, image/TLS/CSP/runtime tests pending |
| R19 | Reviewed commits published to verified GitHub destination | Passed | 5a5b1d3, 35967e2 and 1429309 pushed normally to the verified public sirius287/med-lm-AI/main |
| R20 | Staging deployment and real authenticated browser smoke test verified | Blocked | Requires verified staging accounts, TLS, database, Auth and deployment authorization |

## Current product boundary

- Implemented: email/password auth adapters; server cookie/CSRF session handling;
  manual medication CRUD, schedules, today's doses and append-only dose history;
  English/Hindi/Telugu UI, themes and automated accessibility tests.
- Synthetic-only: fixture extraction, immutable revisions, human transcription
  review and on-demand reports. Explicit dependency injection is required; normal
  app routes remain absent. All 24 medical-information values remain unavailable.
- Unavailable: clinical uploads/OCR, live AI, medicine lookup/licensing, medical
  verification or claims, automatic prescription conversion, notifications, offline
  writes, native desktop targets and deployment.
- iOS compilation requires macOS/Xcode and is not claimed from this Windows host.
  Physical-device accessibility, human translation review and clinical release
  gates remain separate, unverified requirements.

## Execution and evidence

No existing database, role, secret or commit is to be overwritten. Development uses
only the explicitly verified `medlm_dev` target. Tests must create their own isolated
local resources. Upload/analysis grants are excluded from normal runtime setup.
Live provider configuration is entered privately, never in issues, logs or chat.

Local stages A-I: setup/security defects corrected and fresh validation recorded in
[RELEASE_AUDIT.md](RELEASE_AUDIT.md). **17/20 criteria passed (85%)** after
source publication, successful corrective local/hosted validation and the owner's
MIT license decision and private local database setup. Live Auth and staging evidence are separate
gates. The bounded Chrome attempt completed no tests; browser runtime remains
unverified. No clinical validation implied.

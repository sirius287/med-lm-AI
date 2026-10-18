# Phase 3B Chunk 7: injected synthetic Flutter workflow

Date: 2026-10-15. Base/HEAD: 7b3d4eb on main. Implementation is uncommitted and
awaiting human review; nothing is staged or pushed. Chunks 1-6 remain committed.
This is synthetic engineering validation, not clinical validation or a real-user release.

## Implemented boundary

- Separate SyntheticAnalysisHarness widget requiring explicit service injection and
  the existing account scope. No main entry, normal-app route, auth override, developer
  login bypass, fixture-download API or environment-based enable switch.
- Analysis-specific OpenAPI export, strict immutable generated Dart DTOs, semantic
  input/report guards and schema/client parity. Normal/upload-only contracts are unchanged.
- Nine bundled labelled PNGs derived from server fixture definitions: strip, bottle,
  tube, box and prescription, plus empty/ambiguous box and prescription variants.
  Generation validates original/sanitized hashes. Client metadata is descriptive only;
  actual server registration, byte checks, ownership and fencing remain authoritative.
- Authenticated service/controller/provider layer and fixture, observation, review
  and report screens. Original text, nullable fields, alternatives, corrections,
  review history and prescription line identities/dispositions remain separate.
- Complete field coverage and exact literal confirmation; corrections can explicitly
  clear a value. Included prescription lines require complete field review. Final
  decisions close review; unresolved history contributes no accepted transcription.
- All 24 medical-information keys remain unavailable/null with no authoritative source
  checked. Human confirmation never verifies medicine, and synthetic provenance never
  becomes medical evidence. No clinical content is generated or translated.
- Stable per-operation request keys/bodies, frozen uncertain review submissions,
  revision/version checks, explicit new attempts, stale-response rejection and owner
  disposal. Cancellation does not claim physical deletion. Original expiry remains fixed;
  saved text may remain readable after image expiry/cancellation/deletion, but erasure
  removes subsequent access. No offline/image/report persistence is added.
- English/Hindi/Telugu labels, both themes, keyboard navigation, semantics, 200% text,
  narrow layouts and desktop browser-sized layouts. These are not native desktop targets.

The existing upload adapter gained one opt-in resumeCompletion argument, default false.
Ticketless replay may recover status or complete the same already-written immutable
content through existing server checks. It cannot resend bytes, mint a ticket, bypass
checks, extend expiry or silently create another upload. Existing upload tests still pass.
No authentication, manual medication, migration, grant or dependency implementation changed.

## Validation and exact commands

Commands ran from apps/medlm unless a repository-root command is identified. Existing
SDK/cache access required execution outside the filesystem sandbox. No packages were
added or upgraded; later Flutter commands used --no-pub. Build outputs are ignored.

| Command/check | Actual result |
|---|---|
| flutter test --no-pub test/analysis_models_test.dart test/analysis_service_test.dart test/analysis_controller_test.dart test/analysis_ui_test.dart test/analysis_accessibility_test.dart test/analysis_validation_test.dart test/synthetic_upload_test.dart | 71 passed, 0 failed, 0 skipped |
| flutter test --no-pub | 162 passed, 0 failed, 0 skipped |
| flutter analyze --no-pub | No issues found |
| flutter build web --no-pub | Passed, 66.9 seconds; normal main.dart regression build |
| flutter build apk --debug --no-pub | Passed, 72.9 seconds; normal main.dart regression build |
| .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider services/api/tests/test_analysis_client_contract.py services/api/tests/test_manual_contracts.py --tb=short (root) | 3 passed |
| uv run python .local/chunk6_validate.py -p no:cacheprovider (root) | 336 passed, 0 failed, 0 skipped; 271 warnings; 349.67 seconds |
| uv run ruff check services packages database scripts/export_contract.py scripts/generate_analysis_client.py scripts/generate_synthetic_catalog.py (root) | All checks passed |
| git diff --check (root) | Passed; LF/CRLF notices only |

At repository root, with PYTHONPATH=services/api;packages/backend_domain, all six parity
checks passed using .venv/Scripts/python.exe: scripts/export_contract.py --analysis --check,
scripts/export_contract.py --synthetic --check, scripts/export_contract.py --check,
scripts/generate_analysis_client.py --check, scripts/generate_synthetic_catalog.py --check,
and scripts/generate_manual_client.py --check. Initial export also ran through uv run.

Saved output lives in ignored .local/chunk7-focused-flutter.log, chunk7-full-flutter.log,
chunk7-accessibility.log, chunk7-flutter-analysis.log, chunk7-web-build.log,
chunk7-android-build.log, chunk7-backend-tests.log and chunk7-ruff.log.
PowerShell redirected output to these logs and preserved each command's exit code.

An additional command, flutter test --no-pub --platform chrome
test/analysis_models_test.dart test/analysis_service_test.dart
test/analysis_controller_test.dart test/analysis_ui_test.dart
test/analysis_validation_test.dart, stalled at loading the first test. It was interrupted;
zero tests completed and no passing Chrome result is claimed. Its partial output is
.local/chunk7-chrome-tests.log. The cause was not established. Its test browser exited;
pre-existing browser processes were left alone. No security control was weakened.

Focused development runs caught and corrected a generator string escape, test-double
JSON map typing, scoped Riverpod dependency registration, a signed-out provider rebuild
race, test scrolling/semantics cleanup and brace-style lint findings. Final required
validation above passed. The Chrome loading issue remains unverified, not a passing test.

## Database/security evidence

Before any database suite, preflight verified the server's data directory equals the
workspace .local/pgdata, server address/port is 127.0.0.1:15432 and runtime/upload-worker
roles have all four privilege flags false. Shared medlm_test remained at
0005_manual_medications. The existing inspected isolation wrapper created a randomly
named empty suite database and directed all test URLs there; child migration fixtures
created separate random databases. It compared the shared data fingerprint before/after.

The full suite covered existing migration paths, FORCE RLS, cross-user ownership,
composite FKs, immutable history, fences, replay, session/account/CSRF and deletion
safeguards, including Phase 3A regressions. No migrations/grants were edited or added.
Post-run checks found no remaining suite/fixture databases and runtime flags still false.
The workspace test cluster was returned to its initially stopped state.

No live provider was invoked or implemented; server deterministic/disabled adapters
remain unchanged. Flutter tests use explicit synthetic HTTP/service doubles. No real
medical data or credentials were added. Logs use existing fixed application event names;
no user image/text logging or arbitrary storage access was introduced.

## Exact changed files

```text
AI_PIPELINE.md
API_SPEC.md
ARCHITECTURE.md
DEVELOPMENT_PLAN.md
SECURITY.md
apps/medlm/lib/analysis/analysis_report_screen.dart
apps/medlm/lib/analysis/analysis_review_screen.dart
apps/medlm/lib/analysis/analysis_screen.dart
apps/medlm/lib/analysis/analysis_validation.dart
apps/medlm/lib/analysis/analysis_widgets.dart
apps/medlm/lib/analysis/fixture_selection_screen.dart
apps/medlm/lib/analysis/generated/analysis_models.dart
apps/medlm/lib/analysis/generated/synthetic_fixture_catalog.dart
apps/medlm/lib/analysis/synthetic_analysis_controller.dart
apps/medlm/lib/analysis/synthetic_analysis_harness.dart
apps/medlm/lib/analysis/synthetic_analysis_providers.dart
apps/medlm/lib/analysis/synthetic_analysis_service.dart
apps/medlm/lib/l10n/app_en.arb
apps/medlm/lib/l10n/app_hi.arb
apps/medlm/lib/l10n/app_localizations.dart
apps/medlm/lib/l10n/app_localizations_en.dart
apps/medlm/lib/l10n/app_localizations_hi.dart
apps/medlm/lib/l10n/app_localizations_te.dart
apps/medlm/lib/l10n/app_te.arb
apps/medlm/lib/uploads/synthetic_upload_service.dart
apps/medlm/test/analysis_accessibility_test.dart
apps/medlm/test/analysis_controller_test.dart
apps/medlm/test/analysis_models_test.dart
apps/medlm/test/analysis_service_test.dart
apps/medlm/test/analysis_test_support.dart
apps/medlm/test/analysis_ui_test.dart
apps/medlm/test/analysis_validation_test.dart
contracts/README.md
contracts/synthetic-analysis-openapi.json
docs/PHASE_3B_CHUNK_7_REPORT.md
docs/adr/0007-phase-3b-synthetic-analysis.md
scripts/export_contract.py
scripts/generate_analysis_client.py
scripts/generate_synthetic_catalog.py
services/api/tests/test_analysis_client_contract.py
```

Documentation reconciliation updates the development plan's current checkpoint and
marks its pre-commit Chunk 6 authorization/audit paragraphs as historical; ADR sequence
now records committed Chunk 6 and the locally completed Chunk 7. The Chunk 6 audit and
all historical validation counts remain intact. Other documentation describes only
this injected workflow, contract generation and existing privacy boundaries.

## Remaining limits and review gate

No runnable local auth/backend bootstrap was added. Builds validate the normal app;
the injected UI was exercised by Flutter widget/controller tests, not a physical Android
device or completed Chrome run. Interactive Android/Web backend integration, browser
assistive technology and human Hindi/Telugu translation review remain unverified.
Apple/desktop native validation, production auth/storage/operations and source licensing
are outside this chunk. The disposable full-suite wrapper remains ignored/local; CI or
a committed database bootstrap is separate scope. Existing deprecations remain deferred.

There is no real clinical upload, live AI, medicine lookup, authoritative verification,
medical report facts, automatic medication creation, notification or deployment.
Manual medication routes and behavior remain unchanged. No clinical-readiness claim.

Chunk 7 meets the approved automated injected-harness scope and is ready for human
diff/validation review with these limits. HEAD remains 7b3d4eb; all 40 changes are
unstaged/untracked, index empty. Do not commit or push until explicitly approved.

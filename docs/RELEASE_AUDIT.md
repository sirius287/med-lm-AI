# Engineering preview audit and validation

Audit started 2026-10-21; final local checks 2026-10-22. Starting HEAD was
`b8b28b0` on `main`, with an empty index and clean working tree. Existing Phase
1/2/3A/3B history is preserved. No existing migration/grant or domain analysis,
review, report, medication, session or ownership implementation was rewritten.
This is engineering evidence, not clinical validation or a public deployment.

## Hosted portability correction

Commits 5a5b1d3 and 35967e2 were published by normal fast-forward push to the
verified existing public repository/main, without visibility/history changes.
[Initial hosted CI](https://github.com/sirius287/med-lm-AI/actions/runs/39686545036)
exposed one real portability failure: **352 backend tests passed, 1 failed** in
strict bundled fixture parity. All nine PNGs had identical decoded pixels but
different compressed bytes between Windows zlib-ng and Linux zlib. This failure
was not skipped, ignored or fixed by relaxing parity or hash comparisons.

The corrective implementation freezes the existing 11 registered original/clean
image pairs in a server-owned synthetic manifest; all original fixture IDs,
revision numbers and both hashes remain unchanged. Full existing image validation
precedes an explicitly injected, allowlist-matched canonicalizer. Registration
compares fully sanitized content and rejects metadata/trailing chunks in clean
references. The default upload path, auth/RLS, retention/deletion and clinical
gates are unchanged. No migrations, grants, API contracts or Flutter catalog
content changes are required.

Focused results: **9 pure contract/portability tests passed**, then **77 upload/
extraction tests passed** on a new disposable cluster. The corrective full local
run passed **361 tests, 0 failed, 0 skipped** in 363.38 seconds, with the existing
Starlette/httpx warning. Command: `uv run python scripts/test_backend.py --pg-bin
'C:\Program Files\PostgreSQL\18\bin'`. Log:
`.local/test-runs/79e1930c646748a1819bbf49d182b3e8/pytest.log`.
Ruff, its formatting check (84 Python files), unchanged generated catalog parity
and the supplementary current/history secret scan passed. Hosted corrective
validation remains pending; the original hosted Flutter job passed, including
Web and Android builds, while the original backend job failed as recorded above.

Additional corrected paths: AI_PIPELINE.md, SECURITY.md, ADR 0007,
services/api/medlm_api/synthetic_fixtures.py, uploads.py, synthetic_extraction.py,
services/api/medlm_api/fixtures/synthetic-v1.json,
services/api/tests/test_fixture_portability.py and test_synthetic_extraction.py.
The original 45-file set below remains a historical record of the first two commits.

## Findings and smallest fixes

| Classification / severity | Evidence and practical impact | Remediation and regression |
| --- | --- | --- |
| Confirmed configuration blocker / high | `SupabaseGateway._request` refuses missing provider settings; `AuthService.login_web` first needs its cipher/database; `AuthRateLimiter` also needs shared storage/key configuration. A running PostgreSQL service and health 200 do not configure them. | `diagnostics.configuration_issues` names missing MEDLM_ variables without values. `test_original_503_causes_are_separate_and_no_provider_request_occurs` and actual TCP smoke reproduce the different 503s. Live credentials remain external. |
| Configuration defect / medium | Empty copied template encryption settings were parsed as invalid values rather than absent settings. | `Settings` ignores empty environment/dotenv placeholders; tests cover absent values, file loading and process precedence. |
| Security configuration risk / medium | Production could start without a medication replay key or with session/medication key reuse. | Require a distinct medication key in production; hide input values in validation messages. Focused config tests preserve fail-closed behavior. |
| Security dependency risk / high | pip-audit found 26 advisories across certifi 2026.7.22, cryptography 48.0.1 and Pillow 12.3.0. Not every advisory is reachable through MedLM, and normal image admission remains disabled. | Update only these packages to certifi 2026.10.19, cryptography 50.0.2 and Pillow 13.0.0; constrain fixed versions and refresh lockfile. Subsequent audit: 33 backend packages, zero known findings. RSA/ES256 signature, issuer/audience/expiry/tampering and HS256 rejection tests pass. Fixture bytes/catalog remain unchanged. |
| Setup/data-integrity risk / high | Dedicated development resources were absent; the previous guide used manual unverified URLs, printed keys and mentioned obsolete migration 0003. | Guarded `scripts/dev.py init-db`: exact local identity, absent roles/database, empty schema, owner-only migrations, restricted grants, actual runtime login verification, exclusive private env creation. No target override is exposed by CLI. Disposable `--setup-only` exercises the entire flow. |
| Missing test isolation / high | Full DB runner was a machine-specific ignored script tied to a shared baseline. New configuration unit tests initially inherited the full suite URL (4 failures). | `scripts/test_backend.py` creates a NEW SCRAM cluster, verifies directory/identity/freshness, ignores inherited DB URLs and stops only its own server. Unit configuration fixtures isolate environment. Full final application suite passed. |
| Diagnostic test-output risk / medium | An early failed assertion printed a one-time disposable test password. No user/provider/production password was used. | Runner redacts its generated password before saving/printing failure output; the earlier stored log was sanitized and its test cluster stopped. Ignored local test artifacts must never be published. This is not a claim that arbitrary test output can never contain sensitive text. |
| Misleading UI copy / medium | Welcome copy advertised information/reminders while only manual tracking is enabled. An added regression showed the old limitations string was not rendered. | Correct en/hi/te copy and render the unavailable-feature notice on Home; foundation widget test verifies actual visible text. No medication/auth navigation changed. Human language review remains outstanding. |
| Missing reproducibility / medium | No tracked GitHub Actions workflow; no authoritative setup path or deployment preparation. | Pinned CI actions/toolchains, isolated DB regression/setup jobs, Flutter checks/builds, advisory/parity checks; refreshed Windows/README/contribution/disclosure docs. Remote CI execution is a separate gate. |
| Deployment risk / high, still gated | No verified staging target, live Auth, TLS/browser or backup/erasure evidence. Existing SameSite=Lax cookies require same-origin frontend/API. | Same-origin Caddy/API container preparation, explicit secret interpolation and private API port. Do not deploy yet. Proxy address trust/per-client throttling, container builds, CSP/browser and operational gates remain explicit. |

No evidence justified replacing Flutter/FastAPI/PostgreSQL/Supabase, weakening JWT,
CSRF/RLS or changing the clinical pipeline. No external Auth project was contacted.

## Fresh commands and actual results

All PostgreSQL writes/migrations used verified NEW disposable local clusters.
The running service on port 5432 and other projects' databases were not used.
The actual root `.env` remains absent; generated test env files are ignored.

| Command (from repository root unless stated) | Actual result |
| --- | --- |
| `uv run python scripts/test_backend.py --pg-bin 'C:\Program Files\PostgreSQL\18\bin'` | **350 passed, 0 failed, 0 skipped**, 355.82 seconds; 1 existing Starlette/httpx deprecation warning. Log: `.local/test-runs/38994e059c994a93a297daa6926ce31f/pytest.log`. |
| `uv run pytest -q services/api/tests/test_release_checks.py --tb=short` | **3 passed**, 0.04 seconds. Added after the 350-test run; verifies credential-pattern checks also cover test files and never return matched values. These are separate focused results, not an invented 353-test full run. |
| `uv run python scripts/test_backend.py --pg-bin 'C:\Program Files\PostgreSQL\18\bin' --setup-only` | Passed real owner migration, restricted runtime login/grants/FORCE RLS, distinct stable keys, exclusive-file refusal; real root env unchanged. An initial strict-address formatting failure was fixed using `host(inet_server_addr())` and rerun successfully. |
| `uv run pytest -q services/api/tests/test_foundation.py --tb=short` | **9 passed**, including both supported signature algorithms and HS256 rejection. |
| `uv run ruff check services packages database scripts` | Passed. |
| `uv run ruff format --check services packages database scripts` | Passed. |
| `scripts/export_contract.py --check`, `--synthetic --check`, `--analysis --check` using `uv run python` and API/domain PYTHONPATH | All passed; no generated contract/route changes. |
| `scripts/generate_manual_client.py --check`, `scripts/generate_analysis_client.py --check`, `scripts/generate_synthetic_catalog.py --check` | All passed after dependency changes; registered/client fixture parity unchanged. |
| `uv run python scripts/check_localization.py` | **197 keys**, en/hi/te key and placeholder parity passed. |
| `uv run --with PyYAML==6.0.3 python scripts/check_release_config.py` | Static workflow pins/permissions and staging checks passed; Docker Compose `config --quiet` passed without starting the daemon. |
| `uv run python scripts/check_repository.py --history` | Current/new tracked content and local history pattern checks passed. Limited supplementary scanner plus manual diff review; not a guarantee of no secrets. |
| `uv export --frozen --no-dev --no-hashes --format requirements-txt --output-file .local/release-requirements.txt`; `uv tool run --from pip-audit==2.9.0 pip-audit --no-deps --disable-pip --progress-spinner off -r .local/release-requirements.txt -f json -o .local/release-pip-audit-fixed.json` | **33 packages**, no known vulnerabilities after the three targeted updates. Advisory service queried package metadata only. |
| `uv run --with PyYAML==6.0.3 python scripts/audit_flutter_dependencies.py` | OSV checked **102 hosted Pub versions**, zero affected packages. SDK/native/unknown vulnerabilities remain outside coverage. |
| `flutter test test/foundation_test.dart --reporter expanded` (client directory) | **4 passed** after the visible preview notice correction. |
| `flutter analyze` | Passed, no issues. |
| `flutter test --reporter expanded` | **181 passed**, 0 failed; final log `.local/release-flutter-tests.log`. |
| `flutter build web --release --dart-define=APP_ENV=production --no-web-resources-cdn` | Passed, 94.6 seconds; self-hosted resources. Wasm dry-run warnings remain; JS Web build passed and Wasm support is not claimed. |
| `flutter build apk --debug` | Passed, 33.0 seconds, `apps/medlm/build/app/outputs/flutter-apk/app-debug.apk`. Not a signed release/device validation. |
| `uv run python .local/release_smoke.py` (audit-only ignored script) | Actual isolated TCP API: health 200, signed-out session JSON 401, unconfigured login/register JSON 503, allowed CORS 200, synthetic routes 404. Built static index/bootstrap HTTP 200. No real account or browser-runtime success claimed. |
| `git diff --check` | Passed before staging; cached check required at commit. |

Earlier failed runs are not presented as passes: the first full run was
342 passed / 4 environment-isolation failures; the welcome regression initially
failed until its notice was actually displayed. Both were corrected and relevant
checks rerun. Historical phase reports were not rewritten with fresh test counts.

## Dependency and tool review

No application dependency was added. Existing dependencies were narrowly upgraded
for published advisories. QA tools pip-audit 2.9.0 and PyYAML 6.0.3 run in isolated
uv tool environments. Framework/SDK versions were retained. Flutter reports 34
newer constrained package versions; no advisory justified a broad migration.

Installed metadata reports FastAPI/pydantic-settings/SQLAlchemy/PyJWT MIT, Uvicorn
BSD-3-Clause, psycopg LGPL-3.0-only, cryptography Apache-2.0 OR BSD-3-Clause,
Pillow MIT-CMU, certifi MPL-2.0. Metadata is not a legal review. Preserve bundled
third-party notices; source-license choice remains with the owner. No license
for Indian medicine data is presumed.

Current primary references checked 2026-10-22:
[settings precedence](https://github.com/pydantic/pydantic-settings/blob/main/docs/index.md),
[PostgreSQL initialization](https://www.postgresql.org/docs/18/app-initdb.html),
[PGDG Ubuntu installation](https://wiki.postgresql.org/wiki/Apt),
[cryptography security fixes](https://cryptography.io/en/latest/changelog/),
[Pillow 13](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html),
[certifi advisory](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2),
[OSV batch API](https://google.github.io/osv.dev/post-v1-querybatch/),
[Caddy 2.11.7](https://github.com/caddyserver/caddy/releases/tag/v2.11.7).

## Publication and external gates

The exact intended repository was independently verified as
`sirius287/med-lm-AI`, public, unarchived, default branch main, with push permission.
Anonymous Git main matched starting b8b28b0; a push dry run succeeded. Existing
Git credentials were used in memory only for related read-only GitHub metadata;
no value was printed or stored. No visibility change is authorized or performed.

Commits `5a5b1d3` and `35967e2` were published to the verified origin/main by a
normal fast-forward push. The original hosted Flutter job passed; the backend
portability failure and local correction are recorded above. Corrective hosted CI
remains pending. Publication of source does not establish that a staging app works.

Still required: private developer DB/admin setup and Supabase settings; real
registration/email/login/logout and browser-cookie validation; iOS/macOS tooling;
physical-device accessibility; human translation review; source license decision;
verified staging accounts/region/cost/TLS, proxy trust, container builds, backups,
maintenance, erasure/privacy/India release review and real staging smoke tests.
Docker Desktop's daemon is stopped and browser automation has no enabled surfaces;
neither was started/claimed available. No live URL is invented.

A separate bounded local attempt ran `flutter test --platform chrome
test/foundation_test.dart --reporter expanded` from the client directory. It
stalled at loading and completed **0 tests** before the 180-second timeout; only
that attempt's own process tree was stopped. Logs:
`.local/release-chrome-tests.log` and `.local/release-chrome-tests.err`.
This is an unverified browser-runtime check, not a passing end-to-end test.

All 24 report medical-information values stay unavailable/null. No normal medical
upload, provider, source lookup, medical verification, automatic medication,
notification or deployment capability was enabled.

## Exact reviewed release-preparation file set

The 45 paths below are the entire local change set before publication. Ignored
audit scripts/logs, temporary test clusters and build artifacts are not committed.

```text
.dockerignore
.env.example
.github/SECURITY.md
.github/workflows/ci.yml
.gitignore
AGENTS.md
CHANGELOG.md
CONTRIBUTING.md
DEVELOPMENT_PLAN.md
README.md
SECURITY.md
SETUP_WINDOWS.md
alembic.ini
apps/medlm/lib/app/app.dart
apps/medlm/lib/l10n/app_en.arb
apps/medlm/lib/l10n/app_hi.arb
apps/medlm/lib/l10n/app_localizations.dart
apps/medlm/lib/l10n/app_localizations_en.dart
apps/medlm/lib/l10n/app_localizations_hi.dart
apps/medlm/lib/l10n/app_localizations_te.dart
apps/medlm/lib/l10n/app_te.arb
apps/medlm/test/foundation_test.dart
config/backend.env.template
docs/DEPLOYMENT.md
docs/RELEASE_AUDIT.md
docs/RELEASE_CHECKLIST.md
infra/Caddyfile
infra/api.Dockerfile
infra/compose.staging.yml
pyproject.toml
scripts/audit_flutter_dependencies.py
scripts/check_localization.py
scripts/check_release_config.py
scripts/check_repository.py
scripts/dev.py
scripts/test_backend.py
services/api/medlm_api/config.py
services/api/medlm_api/development.py
services/api/medlm_api/diagnostics.py
services/api/medlm_api/main.py
services/api/tests/test_development_setup.py
services/api/tests/test_diagnostics.py
services/api/tests/test_foundation.py
services/api/tests/test_release_checks.py
uv.lock
```

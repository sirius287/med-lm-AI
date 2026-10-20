# API contracts

`synthetic-analysis-openapi.json` is the complete explicitly injected analysis harness
contract, exported with `uv run python scripts/export_contract.py --analysis` (documented
PYTHONPATH: `services/api;packages/backend_domain`). Add `--check` for read-only parity.
It includes existing upload, lifecycle, extraction, review and report schemas but does
not enable any normal-app route. Generate/check the separate strict Dart DTOs with
`scripts/generate_analysis_client.py [--check]` and registered fixture catalog with
`scripts/generate_synthetic_catalog.py [--check]`. No database/provider/credential is
needed for generation. Actual fixture bytes and both hashes are verified during parity.

`synthetic-openapi.json` is exported with `uv run python scripts/export_contract.py --synthetic`. It describes the explicitly injected test-only upload harness, not enabled normal-app capabilities. The existing normal contract remains unchanged. Both contracts are compared against actual FastAPI schemas by the upload regression suite. Flutter's synthetic adapter is explicit and tested; it is not advertised as generated clinical bindings.

`openapi.json` is exported from the implemented FastAPI routes using `scripts/export_contract.py`. Medicine/prescription/reminder services are Python protocols, not fake HTTP endpoints. The Flutter API adapter handles the small foundation contract explicitly; generated clinical DTO/client bindings belong to the phase that introduces those contracts.

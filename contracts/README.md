# API contracts

`synthetic-openapi.json` is exported with `uv run python scripts/export_contract.py --synthetic`. It describes the explicitly injected test-only upload harness, not enabled normal-app capabilities. The existing normal contract remains unchanged. Both contracts are compared against actual FastAPI schemas by the upload regression suite. Flutter's synthetic adapter is explicit and tested; it is not advertised as generated clinical bindings.

`openapi.json` is exported from the implemented FastAPI routes using `scripts/export_contract.py`. Medicine/prescription/reminder services are Python protocols, not fake HTTP endpoints. The Flutter API adapter handles the small foundation contract explicitly; generated clinical DTO/client bindings belong to the phase that introduces those contracts.

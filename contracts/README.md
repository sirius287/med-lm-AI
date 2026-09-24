# API contracts

`openapi.json` is exported from the implemented FastAPI routes using `scripts/export_contract.py`. Medicine/prescription/reminder services are Python protocols, not fake HTTP endpoints. The Flutter API adapter handles the small foundation contract explicitly; generated clinical DTO/client bindings belong to the phase that introduces those contracts.

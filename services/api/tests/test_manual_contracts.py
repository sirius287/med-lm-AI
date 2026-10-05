import importlib.util
import json
from pathlib import Path

from medlm_api.config import Settings
from medlm_api.main import create_app

ROOT = Path(__file__).resolve().parents[3]


def test_openapi_and_generated_manual_binding_parity():
    app = create_app(Settings(_env_file=None, environment="test"))
    try:
        document = json.loads((ROOT / "contracts/openapi.json").read_text())
        assert app.openapi() == document
        spec = importlib.util.spec_from_file_location(
            "manual_codegen", ROOT / "scripts/generate_manual_client.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert (
            module.generate()
            == (ROOT / "apps/medlm/lib/medications/generated/manual_models.dart").read_text()
        )
    finally:
        app.state.database.close()
        app.state.auth.gateway.close()

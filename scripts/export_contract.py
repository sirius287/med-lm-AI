"""Export only implemented routes. Run with the repository API on PYTHONPATH."""
import json
from pathlib import Path

from medlm_api.config import Settings
from medlm_api.main import create_app

app = create_app(Settings(_env_file=None, environment="test", database_url=None,
                          supabase_url=None, supabase_publishable_key=None))
destination = Path(__file__).resolve().parents[1] / "contracts" / "openapi.json"
destination.parent.mkdir(exist_ok=True)
destination.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
app.state.database.close()
app.state.auth.gateway.close()

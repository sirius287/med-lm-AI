"""Export only implemented routes. Run with the repository API on PYTHONPATH."""
import argparse
import json
from pathlib import Path

from medlm_api.config import Settings
from medlm_api.main import create_app

parser = argparse.ArgumentParser()
parser.add_argument("--synthetic", action="store_true", help="Export disabled test-harness routes")
args = parser.parse_args()
# Route registration only: no database, filesystem storage or credentials.
app = create_app(Settings(_env_file=None, environment="test", database_url=None,
                          supabase_url=None, supabase_publishable_key=None),
                 synthetic_uploads=object() if args.synthetic else None)
destination = Path(__file__).resolve().parents[1] / "contracts" / (
    "synthetic-openapi.json" if args.synthetic else "openapi.json")
destination.parent.mkdir(exist_ok=True)
destination.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
app.state.database.close()
app.state.auth.gateway.close()

"""Export only implemented routes. Run with the repository API on PYTHONPATH."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from medlm_api.config import Settings
from medlm_api.main import create_app


def contract_app(*, synthetic=False, analysis=False):
    """Register schemas only. Sentinels cannot execute requests or enable normal app routes."""
    uploads = object() if synthetic or analysis else None
    lifecycle = SimpleNamespace(uploads=uploads) if analysis else None
    child = SimpleNamespace(lifecycle=lifecycle) if analysis else None
    return create_app(
        Settings(
            _env_file=None,
            environment="test",
            database_url=None,
            supabase_url=None,
            supabase_publishable_key=None,
        ),
        synthetic_uploads=uploads,
        synthetic_analyses=lifecycle,
        synthetic_extraction=child,
        synthetic_reviews=child,
        synthetic_reports=child,
    )


def export(*, synthetic=False, analysis=False):
    app = contract_app(synthetic=synthetic, analysis=analysis)
    try:
        return json.dumps(app.openapi(), indent=2) + "\n"
    finally:
        app.state.database.close()
        app.state.auth.gateway.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--synthetic", action="store_true", help="Export upload-only test schemas")
    mode.add_argument(
        "--analysis", action="store_true", help="Export full synthetic analysis schemas"
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    name = (
        "synthetic-analysis-openapi.json"
        if args.analysis
        else ("synthetic-openapi.json" if args.synthetic else "openapi.json")
    )
    destination = Path(__file__).resolve().parents[1] / "contracts" / name
    content = export(synthetic=args.synthetic, analysis=args.analysis)
    if args.check:
        if not destination.exists() or destination.read_text(encoding="utf-8") != content:
            raise SystemExit("API contract is stale")
    else:
        destination.write_text(content, encoding="utf-8")

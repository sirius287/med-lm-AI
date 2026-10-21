"""Static release configuration gates, not deployment validation.

Run: uv run --with PyYAML==6.0.3 python scripts/check_release_config.py
PyYAML is an isolated QA tool, not an application dependency.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main():
    # BaseLoader constructs strings/containers only, never Python objects.
    workflow = yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
    assert workflow["permissions"] == {"contents": "read"}
    assert "pull_request" in workflow["on"] and "pull_request_target" not in workflow["on"]
    for job in workflow["jobs"].values():
        for step in job["steps"]:
            if "uses" in step:
                assert re.fullmatch(r"[\w-]+/[\w-]+@[0-9a-f]{40}", step["uses"])
            if step.get("uses", "").startswith("actions/checkout@"):
                assert step["with"]["persist-credentials"] == "false"
    compose = yaml.load((ROOT / "infra/compose.staging.yml").read_text(), Loader=yaml.BaseLoader)
    api = compose["services"]["api"]
    assert "ports" not in api
    assert api["read_only"] == "true" and api["cap_drop"] == ["ALL"]
    assert api["environment"]["MEDLM_COOKIE_SECURE"] == "true"
    assert api["environment"]["MEDLM_ENVIRONMENT"] == "production"
    print("Static CI pins/permissions and staging isolation checks passed.")
    if shutil.which("docker"):
        env = {k: v for k, v in os.environ.items() if not k.startswith("MEDLM_")}
        # Interpolation-only placeholders. No connection strings, keys or credentials.
        for key in api["environment"]:
            env[key] = "nonsecret-syntax-check-placeholder"
        env["MEDLM_CORS_ORIGINS"] = '["https://preview.example.invalid"]'
        env["MEDLM_PUBLIC_HOST"] = "preview.example.invalid"
        subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                ".env.example",
                "-f",
                "infra/compose.staging.yml",
                "config",
                "--quiet",
            ],
            cwd=ROOT,
            env=env,
            check=True,
        )
        print("Docker Compose syntax passed; no daemon, build, database or deployment was used.")
    else:
        print("Docker Compose syntax NOT RUN: CLI unavailable. No deployment claim.")


if __name__ == "__main__":
    main()

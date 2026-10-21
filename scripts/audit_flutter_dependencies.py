"""Audit hosted locked Pub versions through OSV; never upload source or app data.

Run with the isolated QA parser: uv run --with PyYAML==6.0.3 python scripts/audit_flutter_dependencies.py
Network/API errors fail the check. SDK, native libraries and unknown vulnerabilities
are outside this advisory database's coverage.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main():
    lock = yaml.load((ROOT / "apps/medlm/pubspec.lock").read_text(), Loader=yaml.BaseLoader)
    packages = [
        (name, value["version"])
        for name, value in lock["packages"].items()
        if value["source"] == "hosted"
    ]
    if not packages:
        raise SystemExit("No hosted packages found; audit incomplete")
    queries = [
        {"package": {"name": name, "ecosystem": "Pub"}, "version": version}
        for name, version in packages
    ]
    request = Request(
        "https://api.osv.dev/v1/querybatch",
        data=json.dumps({"queries": queries}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            results = json.load(response)["results"]
    except (URLError, TimeoutError, ValueError, KeyError):
        raise SystemExit("OSV query failed; no passing audit is claimed") from None
    if len(results) != len(packages) or any(r.get("next_page_token") for r in results):
        raise SystemExit("Incomplete OSV response/pagination; audit is not passed")
    findings = [
        {"package": name, "version": version, "ids": [v["id"] for v in row["vulns"]]}
        for (name, version), row in zip(packages, results, strict=True)
        if row.get("vulns")
    ]
    destination = ROOT / ".local/release-flutter-audit.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(
        json.dumps(
            {
                "checked_at": datetime.now(UTC).isoformat(),
                "hosted_packages": len(packages),
                "findings": findings,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    for item in findings:
        print(item["package"] + ": " + ", ".join(item["ids"]))
    print(f"OSV: {len(packages)} hosted Pub versions checked; {len(findings)} affected packages.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())

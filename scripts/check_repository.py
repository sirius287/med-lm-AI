"""Conservative tracked-content secret checks. Prints paths/rules, never matched values.

This is a supplementary check, not a proof that a repository contains no secrets.
Run it before publishing, alongside manual review and GitHub secret scanning.
"""

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    "private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "provider_secret": re.compile(
        rb"(?:sk-(?:proj-)?[A-Za-z0-9_-]{32,}|sb_secret_[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,})"
    ),
    "aws_key": re.compile(rb"\bAKIA[A-Z0-9]{16}\b"),
    "credential_url": re.compile(
        rb"postgres(?:ql)?(?:\+psycopg)?://[^\s:'\"]+:[^\s@'\"]+@[\w.:-]+"
    ),
}


def inspect(name, data):
    issues = []
    for rule, pattern in RULES.items():
        if rule == "credential_url":
            matches = pattern.findall(data)
            # Literal unconfigured placeholder in the historical Windows guide.
            matches = [
                value
                for value in matches
                if b":URL_ENCODED_PASSWORD@" not in value
                and not ("/tests/" in name and b":synthetic@db.invalid" in value)
            ]
            if not matches:
                continue
        elif not pattern.search(data):
            continue
        issues.append((name, rule))
    return issues


def history_issues():
    listing = subprocess.check_output(["git", "rev-list", "--objects", "--all"], cwd=ROOT)
    objects = {}
    for line in listing.splitlines():
        identity, _, path = line.partition(b" ")
        if path:
            objects[identity] = path.decode("utf-8", errors="replace")
    result = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=ROOT,
        input=b"\n".join(objects) + b"\n",
        stdout=subprocess.PIPE,
        check=True,
    )
    data, offset, issues = result.stdout, 0, []
    for identity, name in objects.items():
        end = data.index(b"\n", offset)
        header = data[offset:end].split()
        size = int(header[2])
        content = data[end + 1 : end + 1 + size]
        offset = end + 1 + size + 1
        if header[1] == b"blob":
            issues.extend(inspect(name, content))
    return issues


def check(history=False):
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0")
    untracked = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=ROOT
    ).split(b"\0")
    issues = []
    for raw in set(tracked + untracked):
        if not raw:
            continue
        name = raw.decode("utf-8")
        path = ROOT / name
        if not path.is_file():
            continue
        if path.name == ".env" or (path.name.startswith(".env.") and path.name != ".env.example"):
            issues.append((name, "private_environment_file"))
        issues.extend(inspect(name, path.read_bytes()))
    if history:
        issues.extend(history_issues())
    if issues:
        for name, rule in sorted(set(issues)):
            print(f"Review required: {name} ({rule}); matched value suppressed")
        return 1
    scope = "Tracked/new files and local Git history" if history else "Tracked/new files"
    print(scope + " secret patterns passed. Supplementary check; manual review remains required.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true")
    args = parser.parse_args()
    raise SystemExit(check(args.history))

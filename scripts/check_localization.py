"""Check UI catalog key/placeholder parity without changing generated bindings."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check():
    directory = ROOT / "apps/medlm/lib/l10n"
    catalogs = {
        locale: json.loads((directory / f"app_{locale}.arb").read_text(encoding="utf-8"))
        for locale in ("en", "hi", "te")
    }
    source = catalogs["en"]
    keys = {key for key in source if not key.startswith("@")}
    for locale, catalog in catalogs.items():
        if {key for key in catalog if not key.startswith("@")} != keys:
            raise SystemExit(f"Localization key mismatch: {locale}")
        for key in keys:
            # Placeholder names must match even where metadata is inherited from English.
            import re

            if set(re.findall(r"\{(\w+)\}", catalog[key])) != set(
                re.findall(r"\{(\w+)\}", source[key])
            ):
                raise SystemExit(f"Localization placeholder mismatch: {locale}/{key}")
    print(
        f"Localization parity passed: {len(keys)} keys across en/hi/te. Human review is separate."
    )


if __name__ == "__main__":
    check()

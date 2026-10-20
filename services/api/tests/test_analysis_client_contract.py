"""No DB/provider execution: schema, generated DTO and actual fixture-byte parity."""

import importlib.util
import json
from pathlib import Path

from medlm_api.main import create_app
from medlm_api.synthetic_fixtures import FixtureRegistry, sha256

ROOT = Path(__file__).resolve().parents[3]


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_analysis_schema_and_generated_dart_parity():
    exporter = script("export_contract")
    document = json.loads(exporter.export(analysis=True))
    assert document == json.loads((ROOT / "contracts/synthetic-analysis-openapi.json").read_text())
    assert any("/report" in path for path in document["paths"])
    assert any("/reviews" in path for path in document["paths"])
    assert script("generate_analysis_client").generate() == (
        ROOT / "apps/medlm/lib/analysis/generated/analysis_models.dart"
    ).read_text(encoding="utf-8")
    normal = create_app()
    try:
        assert not any("/analyses" in path for path in normal.openapi()["paths"])
    finally:
        normal.state.database.close()
        normal.state.auth.gateway.close()


def test_bundled_catalog_matches_registered_dual_hashes():
    catalog = script("generate_synthetic_catalog")
    items = catalog.fixtures()
    registry = FixtureRegistry(items)
    assert len(items) == 9
    assert {item.descriptor.document_kind for item in items} == {
        "strip",
        "bottle",
        "tube",
        "box",
        "prescription",
    }
    for item in items:
        d = item.descriptor
        assert d.provenance == "synthetic" and d.purpose == "synthetic_test_not_medical"
        assert sha256(item.original_bytes) == d.original_sha256
        assert sha256(item.sanitized_bytes) == d.sanitized_sha256
        assert registry.resolve(d.original_sha256, d.mime, d.document_kind, item.sanitized_bytes)
    assert catalog.generate() == (
        ROOT / "apps/medlm/lib/analysis/generated/synthetic_fixture_catalog.dart"
    ).read_text(encoding="utf-8")

"""Generate strict, immutable synthetic DTOs from the explicitly injected API schema."""

import argparse
import json
from pathlib import Path

from medlm_domain.report import REPORT_KEYS

ROOT = Path(__file__).resolve().parents[1]
ROOTS = (
    "CreateAnalysis",
    "AnalysisVersion",
    "AnalysisView",
    "LeaseRequest",
    "LeaseView",
    "ExtractRequest",
    "ExtractResponse",
    "ReviewTarget",
    "ReviewContext",
    "HumanReview",
    "ReviewReceipt",
    "AnalysisReport",
)

VALIDATOR = r"""
Never _invalid() => throw const FormatException('Invalid synthetic contract');
dynamic _freeze(dynamic value) => value is Map
    ? Map<String, dynamic>.unmodifiable(value.map((k, v) => MapEntry(k as String, _freeze(v))))
    : value is List ? List<dynamic>.unmodifiable(value.map(_freeze)) : value;
dynamic _copy(dynamic value) => value is Map
    ? value.map((k, v) => MapEntry(k as String, _copy(v)))
    : value is List ? value.map(_copy).toList() : value;
Map<String, dynamic> _checked(String name, Map<String, dynamic> value) {
  _validate(_schemas[name] as Map<String, dynamic>, value);
  return _freeze(value) as Map<String, dynamic>;
}
void _validate(Map<String, dynamic> schema, dynamic value) {
  if (schema.containsKey(r'$ref')) {
    _validate(_schemas[(schema[r'$ref'] as String).split('/').last] as Map<String, dynamic>, value);
    return;
  }
  if (schema['anyOf'] case final List choices) {
    for (final choice in choices) {
      try { _validate(choice as Map<String, dynamic>, value); return; }
      on FormatException { /* Try only the other documented union members. */ }
    }
    _invalid();
  }
  if (schema.containsKey('const') && schema['const'] != value) _invalid();
  if (schema['enum'] case final List values) { if (!values.contains(value)) _invalid(); }
  switch (schema['type']) {
    case 'null': if (value != null) _invalid();
    case 'string':
      if (value is! String) _invalid();
      final size = value.runes.length;
      if (size < (schema['minLength'] as int? ?? 0) ||
          size > (schema['maxLength'] as int? ?? 1000000)) { _invalid(); }
      if (schema['pattern'] case final String pattern) {
        if (!RegExp(pattern).hasMatch(value)) _invalid();
      }
      if (schema['format'] == 'uuid' &&
          !RegExp(r'^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$').hasMatch(value)) { _invalid(); }
      if (schema['format'] == 'date-time' && DateTime.tryParse(value) == null) _invalid();
    case 'integer': if (value is! int) _invalid(); _number(schema, value);
    case 'number': if (value is! num || !value.isFinite) _invalid(); _number(schema, value);
    case 'boolean': if (value is! bool) _invalid();
    case 'array':
      if (value is! List) _invalid();
      if (value.length < (schema['minItems'] as int? ?? 0) ||
          value.length > (schema['maxItems'] as int? ?? 10000)) { _invalid(); }
      if (schema['items'] case final Map<String, dynamic> item) {
        for (final element in value) { _validate(item, element); }
      }
    case 'object':
      if (value is! Map<String, dynamic>) _invalid();
      final data = value;
      final properties = schema['properties'] as Map<String, dynamic>? ?? {};
      for (final key in schema['required'] as List? ?? []) {
        if (!data.containsKey(key)) _invalid();
      }
      if (data.length < (schema['minProperties'] as int? ?? 0) ||
          data.length > (schema['maxProperties'] as int? ?? 10000)) { _invalid(); }
      for (final entry in data.entries) {
        if (properties.containsKey(entry.key)) {
          try { _validate(properties[entry.key] as Map<String, dynamic>, entry.value); }
          on FormatException catch (error) { throw FormatException('${entry.key}: ${error.message}'); }
        } else if (schema['additionalProperties'] == false) { _invalid(); }
        else if (schema['additionalProperties'] case final Map<String, dynamic> extra) {
          _validate(extra, entry.value);
        }
      }
    default: _invalid();
  }
}
void _number(Map<String, dynamic> schema, num value) {
  if (!value.isFinite || (schema['minimum'] != null && value < schema['minimum']) ||
      (schema['maximum'] != null && value > schema['maximum']) ||
      (schema['exclusiveMinimum'] != null && value <= schema['exclusiveMinimum']) ||
      (schema['exclusiveMaximum'] != null && value >= schema['exclusiveMaximum'])) { _invalid(); }
}
"""


def camel(name):
    if name == "final":
        return "isFinal"
    return name.split("_")[0] + "".join(part.title() for part in name.split("_")[1:])


def generate():
    schemas = json.loads((ROOT / "contracts/synthetic-analysis-openapi.json").read_text())[
        "components"
    ]["schemas"]
    selected = {}

    def include(name):
        if name in selected:
            return
        selected[name] = schemas[name]

        def walk(value):
            if isinstance(value, dict):
                if "$ref" in value:
                    include(value["$ref"].split("/")[-1])
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(schemas[name])

    for name in ROOTS:
        include(name)

    def shape(schema, expr):
        if "anyOf" in schema:
            nonnull = [s for s in schema["anyOf"] if s.get("type") != "null"]
            if len(nonnull) != 1:
                raise ValueError("Unsupported synthetic union")
            type_, read = shape(nonnull[0], expr)
            return type_ + "?", f"{expr} == null ? null : {read}"
        if "$ref" in schema:
            name = schema["$ref"].split("/")[-1]
            if "properties" in selected[name]:
                return name, f"{name}.fromJson({expr} as Map<String, dynamic>)"
            return shape(selected[name], expr)
        kind = schema["type"]
        if kind == "array":
            if not schema.get("items"):
                return "List<dynamic>", f"List<dynamic>.unmodifiable({expr} as List)"
            inner, read = shape(schema["items"], "item")
            return (
                f"List<{inner}>",
                f"List<{inner}>.unmodifiable(({expr} as List).map((item) => {read}))",
            )
        if kind == "object":
            extra = schema.get("additionalProperties")
            if isinstance(extra, dict):
                inner, read = shape(extra, "item")
                return (
                    f"Map<String, {inner}>",
                    f"Map<String, {inner}>.unmodifiable(({expr} as Map<String, dynamic>).map((key, item) => MapEntry(key, {read})))",
                )
            return "Map<String, dynamic>", f"{expr} as Map<String, dynamic>"
        type_ = {
            "string": "String",
            "integer": "int",
            "number": "num",
            "boolean": "bool",
            "null": "Null",
        }[kind]
        return type_, "null" if kind == "null" else f"{expr} as {type_}"

    lines = [
        "// Generated by scripts/generate_analysis_client.py. Do not edit.",
        "import 'dart:convert';",
        "",
        "final _schemas = jsonDecode(r'''",
        json.dumps(selected, separators=(",", ":")),
        "''') as Map<String, dynamic>;",
        VALIDATOR,
        "const medicalInformationKeys = <String>" + json.dumps(list(REPORT_KEYS)) + ";",
        "const medicineObservationKeys = <String>"
        + json.dumps(list(schemas["MedicineFields"]["properties"]))
        + ";",
        "const prescriptionObservationKeys = <String>"
        + json.dumps(list(schemas["PrescriptionFields"]["properties"]))
        + ";",
    ]
    for name, schema in selected.items():
        if "properties" not in schema:
            continue
        lines += [
            f"class {name} {{",
            f"  {name}.fromJson(Map<String, dynamic> json) : _json = _checked('{name}', json);",
            "  final Map<String, dynamic> _json;",
            "  Map<String, dynamic> toJson() => _copy(_json) as Map<String, dynamic>;",
        ]
        for wire, prop in schema["properties"].items():
            expr = f"_json['{wire}']"
            if "default" in prop and prop["default"] is not None:
                default = json.dumps(prop["default"])
                expr = f"(_json.containsKey('{wire}') ? _json['{wire}'] : {default})"
            type_, read = shape(prop, expr)
            lines.append(f"  {type_} get {camel(wire)} => {read};")
        lines += ["}", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = ROOT / "apps/medlm/lib/analysis/generated/analysis_models.dart"
    content = generate()
    if args.check:
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            raise SystemExit("Synthetic analysis bindings are stale")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

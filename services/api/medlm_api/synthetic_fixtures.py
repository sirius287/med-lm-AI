"""Explicit in-memory registration only; no paths, URLs, discovery or medical data."""

import base64
import hashlib
import io
import json
import struct
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from uuid import NAMESPACE_URL, uuid5

from medlm_domain.analysis import ExtractionResult
from medlm_domain.extraction import ExtractionRequest, FixtureDescriptor
from PIL import Image, ImageDraw, PngImagePlugin

from medlm_api.images import MIME_FORMATS, validate_image


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FixtureInvalid(ValueError):
    pass


@lru_cache(maxsize=1)
def _canonical_images():
    """Explicit package asset, never a client path, directory scan or download."""
    document = json.loads(
        (Path(__file__).parent / "fixtures/synthetic-v1.json").read_text(encoding="utf-8")
    )
    if document["schema_version"] != 1 or document["purpose"] != "synthetic_test_not_medical":
        raise FixtureInvalid("Invalid canonical catalog")
    records = {}
    for row in document["fixtures"]:
        if set(row) != {"descriptor", "original_base64", "sanitized_base64"}:
            raise FixtureInvalid("Invalid canonical fixture")
        descriptor = FixtureDescriptor.model_validate(row["descriptor"])
        original = base64.b64decode(row["original_base64"], validate=True)
        sanitized = base64.b64decode(row["sanitized_base64"], validate=True)
        if (
            descriptor.fixture_id in records
            or descriptor.fixture_revision != 1
            or sha256(original) != descriptor.original_sha256
            or sha256(sanitized) != descriptor.sanitized_sha256
        ):
            raise FixtureInvalid("Canonical fixture identity mismatch")
        records[descriptor.fixture_id] = (descriptor, original, sanitized)
    return MappingProxyType(records)


def _plain_png(data):
    """Canonical server images may contain no ancillary/trailing metadata."""
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return False
    offset = 8
    while offset + 12 <= len(data):
        size = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4 : offset + 8]
        offset += size + 12
        if offset > len(data) or kind not in (b"IHDR", b"IDAT", b"IEND"):
            return False
        if kind == b"IEND":
            return size == 0 and offset == len(data)
    return False


@dataclass(frozen=True)
class RegisteredFixture:
    descriptor: FixtureDescriptor
    original_bytes: bytes
    sanitized_bytes: bytes
    observations: ExtractionResult


class FixtureRegistry:
    def __init__(self, fixtures: tuple[RegisteredFixture, ...]):
        registry = {}
        identities = set()
        normalized = {}
        for item in fixtures:
            d = FixtureDescriptor.model_validate(item.descriptor.model_dump())
            if (
                d.fixture_revision != 1
                or (d.fixture_id, d.fixture_revision) in identities
                or d.original_sha256 in registry
                or sha256(item.original_bytes) != d.original_sha256
                or sha256(item.sanitized_bytes) != d.sanitized_sha256
                or not _plain_png(item.sanitized_bytes)
                or item.observations.document_kind != d.document_kind
            ):
                raise FixtureInvalid("Invalid fixture registration")
            # zlib/zlib-ng encode identical pixels differently across hosts. Both
            # original and canonical bytes still pass the full existing sanitizer.
            clean = validate_image(item.original_bytes, d.mime, 10485760, 40000000)
            reference = validate_image(item.sanitized_bytes, "image/png", 10485760, 40000000)
            if clean != reference:
                raise FixtureInvalid("Canonical image content mismatch")
            normalized[d.original_sha256] = reference
            registry[d.original_sha256] = item
            identities.add((d.fixture_id, d.fixture_revision))
        self._registered = MappingProxyType(registry)
        self._normalized = MappingProxyType(normalized)

    @property
    def original_hashes(self):
        return frozenset(self._registered)

    def canonical_input(self, original_hash: str, normalized: bytes) -> bytes:
        """Only an exact registered original AND equivalent sanitized content."""
        item = self._registered.get(original_hash)
        if item is None or normalized != self._normalized[original_hash]:
            raise FixtureInvalid("Invalid canonical image binding")
        return item.sanitized_bytes

    def resolve(self, original_hash: str, mime: str, kind: str, data: bytes) -> ExtractionRequest:
        item = self._registered.get(original_hash)
        if item is None:
            raise FixtureInvalid("Unknown fixture")
        d = item.descriptor
        if d.mime != mime or d.document_kind != kind or sha256(data) != d.sanitized_sha256:
            raise FixtureInvalid("Fixture content mismatch")
        return ExtractionRequest(d, data)

    def observations(self, request: ExtractionRequest) -> ExtractionResult:
        d = request.fixture
        validated = self.resolve(
            d.original_sha256, d.mime, d.document_kind, request.sanitized_bytes
        )
        if validated.fixture != d:
            raise FixtureInvalid("Fixture revision or metadata mismatch")
        return self._registered[d.original_sha256].observations.model_copy(deep=True)


def controlled_fixture(
    kind: str, *, empty=False, ambiguous=False, mime="image/png"
) -> RegisteredFixture:
    """Deterministic labelled test image, never a medicine/prescription facsimile."""
    identity = f"synthetic_{kind}_{'empty' if empty else 'ambiguous' if ambiguous else 'literal'}"
    if mime not in MIME_FORMATS:
        raise FixtureInvalid("Unsupported fixture MIME")
    if mime != "image/png":
        identity += "_" + MIME_FORMATS[mime].lower()
    literal = "TEST ITEM A"
    canonical = _canonical_images().get(identity)
    if canonical:
        registered, original, sanitized = canonical
        if registered.document_kind != kind or registered.mime != mime:
            raise FixtureInvalid("Canonical document mismatch")
    else:
        # Additional local test descriptors are not silently added to the bundled catalog.
        image = Image.new("RGB", (640, 160), "white")
        draw = ImageDraw.Draw(image)
        draw.text((8, 8), "SYNTHETIC TEST ONLY - NOT MEDICAL INFORMATION", fill="black")
        draw.text((8, 30), identity, fill="black")
        if not empty:
            draw.text((8, 55), literal, fill="black")
            if kind == "prescription":
                draw.text((8, 80), "TEST LINE B", fill="black")
                draw.text((8, 105), "Line A strength: STRENGTH TOKEN; dose: absent", fill="black")
        output = io.BytesIO()
        info = PngImagePlugin.PngInfo()
        info.add_text("synthetic-fixture", identity + ":1")
        image.save(
            output, format=MIME_FORMATS[mime], **({"pnginfo": info} if mime == "image/png" else {})
        )
        original = output.getvalue()
        sanitized = validate_image(original, mime, 10485760, 40000000)

    def field(raw=None):
        return dict(
            raw_text=raw,
            normalized_value=raw,
            unit=None,
            bounding_box=None,
            ambiguity_reason="Synthetic ambiguity" if ambiguous and raw else None,
            alternatives=("TEST ITEM B",) if ambiguous and raw else (),
            confidence=None,
        )

    if kind == "prescription":
        lines = []
        for ordinal, raw in enumerate((literal, "TEST LINE B")):
            fields = {
                key: field()
                for key in (
                    "medicine",
                    "strength",
                    "dose",
                    "frequency",
                    "route",
                    "duration",
                    "time",
                    "food_instruction",
                    "special_instruction",
                )
            }
            fields["medicine"] = field(None if empty else raw)
            if ordinal == 0 and not empty:
                fields["strength"] = field("STRENGTH TOKEN")
            lines.append(
                dict(
                    line_id=uuid5(NAMESPACE_URL, identity + str(ordinal)),
                    ordinal=ordinal,
                    fields=fields,
                )
            )
        result = ExtractionResult(document_kind=kind, medicine=None, lines=lines)
    else:
        fields = {
            key: field()
            for key in ("medicine", "strength", "ingredients", "dosage_form", "manufacturer")
        }
        fields["medicine"] = field(None if empty else literal)
        result = ExtractionResult(document_kind=kind, medicine=fields, lines=())
    descriptor = FixtureDescriptor(
        fixture_id=identity,
        fixture_revision=1,
        document_kind=kind,
        mime=mime,
        original_sha256=sha256(original),
        sanitized_sha256=sha256(sanitized),
        provenance="synthetic",
        purpose="synthetic_test_not_medical",
        observation_schema_version=1,
    )
    return RegisteredFixture(descriptor, original, sanitized, result)


def controlled_catalog() -> tuple[RegisteredFixture, ...]:
    # No automatic registration: the harness must explicitly inject this catalog.
    return tuple(
        controlled_fixture(kind) for kind in ("strip", "bottle", "tube", "box", "prescription")
    )

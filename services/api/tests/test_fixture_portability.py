"""Exercise a genuinely different PNG encoder without relaxing hash validation."""

import io
from dataclasses import replace

import pytest
from medlm_api.images import validate_image
from medlm_api.synthetic_fixtures import FixtureInvalid, FixtureRegistry, controlled_fixture, sha256
from medlm_api.uploads import SyntheticUploads
from PIL import Image, PngImagePlugin


def different_png_encoder(monkeypatch):
    original = Image.Image.save

    def save(image, target, format=None, **parameters):
        if format == "PNG":
            parameters["compress_level"] = 0
        return original(image, target, format=format, **parameters)

    monkeypatch.setattr(Image.Image, "save", save)


@pytest.mark.parametrize("mime", ["image/png", "image/jpeg", "image/webp"])
def test_registered_identity_and_dual_hashes_survive_different_encoder(monkeypatch, mime):
    expected = controlled_fixture("box", mime=mime)
    different_png_encoder(monkeypatch)
    current = controlled_fixture("box", mime=mime)
    assert current == expected
    runtime = validate_image(current.original_bytes, mime, 10485760, 40000000)
    assert runtime != current.sanitized_bytes  # Exercise the actual failed CI condition.
    registry = FixtureRegistry((current,))
    canonical = registry.canonical_input(current.descriptor.original_sha256, runtime)
    assert canonical == expected.sanitized_bytes
    assert sha256(canonical) == expected.descriptor.sanitized_sha256
    assert registry.resolve(current.descriptor.original_sha256, mime, "box", canonical)


def test_wrong_hash_or_content_cannot_select_canonical_fixture():
    item = controlled_fixture("box")
    registry = FixtureRegistry((item,))
    for checksum, data in (
        ("f" * 64, item.sanitized_bytes),
        (item.descriptor.original_sha256, b"changed"),
    ):
        with pytest.raises(FixtureInvalid):
            registry.canonical_input(checksum, data)


@pytest.mark.parametrize("change", ["metadata", "trailing"])
def test_hash_matching_canonical_fixture_cannot_retain_metadata(change):
    item = controlled_fixture("box")
    if change == "metadata":
        output = io.BytesIO()
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("synthetic-private-test", "must be rejected")
        with Image.open(io.BytesIO(item.sanitized_bytes)) as image:
            image.save(output, format="PNG", pnginfo=metadata)
        bad = output.getvalue()
    else:
        bad = item.sanitized_bytes + b"trailing synthetic test data"
    descriptor = item.descriptor.model_copy(update={"sanitized_sha256": sha256(bad)})
    with pytest.raises(FixtureInvalid):
        FixtureRegistry((replace(item, descriptor=descriptor, sanitized_bytes=bad),))


def test_upload_binding_is_exact_allowlisted_and_cannot_be_replaced():
    item = controlled_fixture("box")
    registry = FixtureRegistry((item,))
    service = SyntheticUploads(object(), registry.original_hashes)
    assert service._canonicalize is None  # Ordinary synthetic upload validation stays unchanged.
    with pytest.raises(ValueError):
        service.bind_fixture_images(frozenset(), registry.canonical_input)
    service.bind_fixture_images(registry.original_hashes, registry.canonical_input)
    service.bind_fixture_images(registry.original_hashes, registry.canonical_input)
    with pytest.raises(ValueError):
        service.bind_fixture_images(registry.original_hashes, lambda *_: b"changed")
    assert service._canonicalize == registry.canonical_input

"""Synthetic extraction boundary. Provider output has no acceptance authority."""

from dataclasses import dataclass
from typing import Annotated, Literal, Protocol

from pydantic import Field

from medlm_domain.analysis import Contract, ExtractionResult

Identifier = Annotated[str, Field(pattern=r"^[a-z0-9_-]{1,80}$")]
Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class FixtureDescriptor(Contract):
    fixture_id: Identifier
    fixture_revision: Annotated[int, Field(strict=True, gt=0)]
    document_kind: Literal["strip", "bottle", "tube", "box", "prescription"]
    mime: Literal["image/jpeg", "image/png", "image/webp"]
    original_sha256: Hash
    sanitized_sha256: Hash
    input_mime: Literal["image/png"] = "image/png"
    provenance: Literal["synthetic"]
    purpose: Literal["synthetic_test_not_medical"]
    observation_schema_version: Literal[1]


class ProviderIdentity(Contract):
    provider_id: Identifier
    model_id: Identifier
    pipeline_version: Identifier


class ExtractionMetadata(ProviderIdentity):
    fixture_revision: Annotated[int, Field(strict=True, gt=0)]
    sanitized_sha256: Hash


@dataclass(frozen=True)
class ExtractionRequest:
    fixture: FixtureDescriptor
    sanitized_bytes: bytes


class ExtractionAdapter(Protocol):
    @property
    def identity(self) -> ProviderIdentity: ...
    def available(self) -> bool: ...
    def extract(self, request: ExtractionRequest) -> ExtractionResult: ...


SAFE_ERRORS = {
    "provider_disabled": "Extraction provider is unavailable.",
    "fixture_invalid": "Controlled synthetic fixture binding is invalid.",
    "adapter_failure": "Synthetic extraction could not finish.",
    "invalid_output": "Extraction output did not pass validation.",
    "no_observations": "No text was observed; input is required.",
}

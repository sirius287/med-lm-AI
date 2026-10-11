"""No network transports, SDK, environment access, credentials or provider fallback."""

from typing import Literal

from medlm_domain.analysis import Contract, ExtractionResult
from medlm_domain.extraction import ExtractionRequest, ProviderIdentity

from medlm_api.errors import AppError
from medlm_api.synthetic_fixtures import FixtureRegistry


class DeterministicAdapter:
    identity = ProviderIdentity(
        provider_id="synthetic",
        model_id="deterministic-v1",
        pipeline_version="synthetic-extraction-v1",
    )

    def __init__(self, registry: FixtureRegistry):
        self.registry = registry

    def available(self) -> bool:
        return True

    def extract(self, request: ExtractionRequest) -> ExtractionResult:
        return self.registry.observations(request)


class AstraBoundaryConfig(Contract):
    enabled: Literal[False] = False
    provider_id: Literal["openai"] = "openai"
    model_id: Literal["unconfigured"] = "unconfigured"


class DisabledAstraAdapter:
    """Future translation boundary only. Cannot be enabled in this chunk."""

    identity = ProviderIdentity(
        provider_id="openai", model_id="unconfigured", pipeline_version="disabled-boundary-v1"
    )

    def __init__(self, config: AstraBoundaryConfig | None = None):
        self.config = config or AstraBoundaryConfig()

    def available(self) -> bool:
        return False

    def extract(self, request: ExtractionRequest) -> ExtractionResult:
        raise AppError(503, "provider_disabled", "Extraction provider is unavailable.")

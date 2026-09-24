from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class AnalysisContext:
    user_id: UUID
    country: str
    locale: str


class AIService(Protocol):
    async def available(self) -> bool: ...


class VisionService(Protocol):
    async def extract(self, image: bytes, context: AnalysisContext) -> dict: ...


class MedicineIdentificationService(Protocol):
    async def candidates(self, observations: dict, context: AnalysisContext) -> list[dict]: ...


class MedicineInformationService(Protocol):
    async def evidence(self, product_id: str, context: AnalysisContext) -> list[dict]: ...


class PrescriptionAnalysisService(Protocol):
    async def draft(self, image: bytes, context: AnalysisContext) -> dict: ...


class OwnedRepository(Protocol):
    def get(self, user_id: UUID, record_id: UUID) -> dict | None: ...


class TemporaryStorage(Protocol):
    def put(self, owner: UUID, data: bytes) -> UUID: ...
    def read(self, owner: UUID, key: UUID) -> bytes: ...
    def delete(self, owner: UUID, key: UUID) -> None: ...
    def purge_expired(self) -> int: ...


@dataclass(frozen=True)
class MarketPolicy:
    country: str
    locales: tuple[str, ...]
    verified_identification_enabled: bool = False


MARKETS = {
    "IN": MarketPolicy("IN", ("en-IN", "hi-IN", "te-IN")),
    "US": MarketPolicy("US", ("en-US",)),
}

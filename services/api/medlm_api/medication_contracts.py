"""Public response shapes; generated client models derive from these contracts."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from medlm_domain.manual_medications import ScheduleInput
from pydantic import BaseModel


class MedicationView(BaseModel):
    id: UUID
    display_name: str
    strength_text: str | None
    dose_text: str
    route_text: str | None
    instructions: str | None
    version: int
    origin: Literal["manual"] = "manual"
    verification_status: Literal["unverified"] = "unverified"
    deleted_at: datetime | None
    schedule: ScheduleInput | None


class MedicationPage(BaseModel):
    items: list[MedicationView]
    next_cursor: str | None


class PlannedDose(BaseModel):
    planned_at: datetime
    original_local_time: str


class PreviewView(BaseModel):
    proposal_hash: str
    expires_at: datetime
    medication_version: int
    occurrences: list[PlannedDose]
    warnings: list[str]


class OccurrenceView(BaseModel):
    id: UUID
    medication_id: UUID
    planned_at: datetime
    original_local_time: str | None
    dose_snapshot: dict[str, Any]
    status: Literal["pending", "taken", "skipped", "cancelled"]
    version: int
    latest_event_id: UUID | None
    actionable: bool


class OccurrencePage(BaseModel):
    items: list[OccurrenceView]
    next_cursor: str | None


class EventView(BaseModel):
    event_id: UUID
    occurrence: OccurrenceView


class HistoryView(BaseModel):
    id: UUID
    occurrence_id: UUID
    kind: str
    client_at: datetime
    recorded_at: datetime
    supersedes_event_id: UUID | None
    payload: dict[str, Any]
    dose_snapshot: dict[str, Any]
    original_local_time: str | None


class HistoryPage(BaseModel):
    items: list[HistoryView]
    next_cursor: str | None


class MaterializeView(BaseModel):
    generated: int

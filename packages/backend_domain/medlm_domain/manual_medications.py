"""Manual records are user assertions, never verified medical information."""

import re
from datetime import date, datetime, time
from decimal import Decimal
from functools import lru_cache
from importlib.resources import files
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator


@lru_cache(maxsize=1024)
def iana_zone(name: str) -> ZoneInfo:
    """Use locked tzdata consistently, independent of host OS database versions."""
    if not re.fullmatch(r"[A-Za-z0-9_+-]+(?:/[A-Za-z0-9_+-]+)*", name):
        raise ValueError("Invalid timezone")
    if len(name) > 100 or "\\" in name or any(part in ("", ".", "..") for part in name.split("/")):
        raise ValueError("Invalid timezone")
    try:
        with files("tzdata.zoneinfo").joinpath(name).open("rb") as source:
            return ZoneInfo.from_file(source, key=name)
    except (OSError, ValueError) as exc:
        raise ZoneInfoNotFoundError(name) from exc


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MedicationInput(Contract):
    display_name: str = Field(min_length=1, max_length=200)
    strength_text: str | None = Field(default=None, max_length=200)
    dose_text: str = Field(min_length=1, max_length=500)
    route_text: str | None = Field(default=None, max_length=200)
    instructions: str | None = Field(default=None, max_length=2000)


class ScheduleInput(Contract):
    kind: Literal["daily_times", "weekdays", "fixed_interval", "one_time"]
    time_zone: str = Field(max_length=100)
    start_date: date
    end_date: date | None = None
    open_ended: bool = False
    local_times: list[time] = Field(default_factory=list, max_length=12)
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    interval_hours: Decimal | None = Field(default=None, ge=1, le=8760, decimal_places=2)
    anchor_at: datetime | None = None
    one_time_at: datetime | None = None

    @model_validator(mode="after")
    def coherent(self):
        if not 2020 <= self.start_date.year <= 2100 or (
            self.end_date and not 2020 <= self.end_date.year <= 2100
        ):
            raise ValueError("Schedule dates must be between 2020 and 2100")
        try:
            iana_zone(self.time_zone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Unsupported timezone") from exc
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("End must not precede start")
        if (self.end_date is None) != self.open_ended:
            raise ValueError("Choose an end date or explicitly choose open-ended")
        if any(t.tzinfo or t.second or t.microsecond for t in self.local_times):
            raise ValueError("Clock times use local hours and minutes")
        if len(set(self.local_times)) != len(self.local_times):
            raise ValueError("Duplicate clock time")
        if len(set(self.weekdays)) != len(self.weekdays) or any(
            d < 0 or d > 6 for d in self.weekdays
        ):
            raise ValueError("Weekdays must be unique Monday=0 through Sunday=6")
        for instant in (self.anchor_at, self.one_time_at):
            if instant and (instant.tzinfo is None or instant.utcoffset() is None):
                raise ValueError("An explicit UTC offset is required")
        if self.kind in ("daily_times", "weekdays"):
            if not self.local_times or self.interval_hours or self.anchor_at or self.one_time_at:
                raise ValueError("Calendar schedules require only clock times")
            if bool(self.weekdays) != (self.kind == "weekdays"):
                raise ValueError("Selected weekdays required only for weekday schedules")
        elif self.kind == "fixed_interval":
            if (
                not self.interval_hours
                or not self.anchor_at
                or self.local_times
                or self.weekdays
                or self.one_time_at
            ):
                raise ValueError("Interval schedules require an explicit interval and anchor")
        elif (
            not self.one_time_at
            or self.local_times
            or self.weekdays
            or self.interval_hours
            or self.anchor_at
        ):
            raise ValueError("One-time schedules require one instant")
        instant = self.one_time_at if self.kind == "one_time" else self.anchor_at
        if instant:
            day = instant.astimezone(iana_zone(self.time_zone)).date()
            if day < self.start_date or (self.end_date and day > self.end_date):
                raise ValueError("Anchor must lie inside the schedule dates")
        return self


class ActivationInput(Contract):
    schedule: ScheduleInput
    proposal_hash: str = Field(min_length=64, max_length=64)
    expires_at: datetime
    medication_version: int = Field(ge=1)


class MaterializeInput(Contract):
    from_date: date
    to_date: date

    @model_validator(mode="after")
    def bounded(self):
        if not 0 <= (self.to_date - self.from_date).days <= 89:
            raise ValueError("Choose a range of at most 90 days")
        return self


class DoseEventInput(Contract):
    event_id: UUID
    type: Literal["taken", "skipped", "corrected"]
    expected_version: int = Field(ge=1)
    client_at: datetime
    supersedes_event_id: UUID | None = None
    corrected_status: Literal["taken", "skipped", "pending"] | None = None

    @model_validator(mode="after")
    def coherent(self):
        if self.client_at.tzinfo is None:
            raise ValueError("An explicit UTC offset is required")
        if self.type == "corrected":
            if not self.supersedes_event_id or not self.corrected_status:
                raise ValueError("Correction must identify the event and replacement status")
        elif self.supersedes_event_id or self.corrected_status:
            raise ValueError("Correction fields are not allowed for a dose action")
        return self

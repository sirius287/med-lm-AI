"""Pure synthetic-analysis contracts. No providers, persistence or acceptance side effects."""

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


Text = Annotated[str, Field(strict=True, min_length=1, max_length=2000)]
Coordinate = Annotated[float, Field(strict=True, ge=0, le=1)]


class AnalysisState(StrEnum):
    QUEUED = "queued"
    VALIDATING = "validating"
    EXTRACTING = "extracting"
    RETRIEVING = "retrieving"
    VALIDATING_OUTPUT = "validating_output"
    COMPLETED = "completed"
    NEEDS_INPUT = "needs_input"
    FAILED = "failed"
    CANCELLED = "cancelled"


def transition(current: AnalysisState, target: AnalysisState) -> AnalysisState:
    """Terminal results never reopen; re-extraction requires a new job/revision."""
    stages = (
        AnalysisState.QUEUED,
        AnalysisState.VALIDATING,
        AnalysisState.EXTRACTING,
        AnalysisState.RETRIEVING,
        AnalysisState.VALIDATING_OUTPUT,
        AnalysisState.COMPLETED,
    )
    current, target = AnalysisState(current), AnalysisState(target)
    if current not in stages[:-1]:
        raise ValueError("Terminal analysis cannot transition")
    allowed = {
        stages[stages.index(current) + 1],
        AnalysisState.FAILED,
        AnalysisState.CANCELLED,
        AnalysisState.NEEDS_INPUT,
    }
    if target not in allowed:
        raise ValueError("Invalid analysis transition")
    return target


class BoundingBox(Contract):
    x: Coordinate
    y: Coordinate
    width: Annotated[float, Field(strict=True, gt=0, le=1)]
    height: Annotated[float, Field(strict=True, gt=0, le=1)]

    @model_validator(mode="after")
    def contained(self):
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError("Box must be inside image")
        return self


class Confidence(Contract):
    source: Literal["provider", "fixture"]
    score: Annotated[float, Field(strict=True, ge=0, le=1)] | None
    calibration: Literal["uncalibrated"] = "uncalibrated"


class ExtractionField(Contract):
    # Required nullable fields distinguish explicit absence from omitted output.
    raw_text: Text | None
    normalized_value: Text | None
    unit: Text | None
    bounding_box: BoundingBox | None
    ambiguity_reason: Text | None
    alternatives: tuple[Text, ...] = Field(max_length=10)
    confidence: Confidence | None

    @model_validator(mode="after")
    def observed_only(self):
        if self.raw_text is None and (self.normalized_value is not None or self.unit is not None):
            raise ValueError("Absent text cannot supply a normalized value or unit")
        if self.raw_text is not None and not self.raw_text.strip():
            raise ValueError("Use null for absent text")
        if self.alternatives and not self.ambiguity_reason:
            raise ValueError("Alternatives require an ambiguity reason")
        return self


class MedicineFields(Contract):
    medicine: ExtractionField
    strength: ExtractionField
    ingredients: ExtractionField
    dosage_form: ExtractionField
    manufacturer: ExtractionField


class PrescriptionFields(Contract):
    medicine: ExtractionField
    strength: ExtractionField
    dose: ExtractionField
    frequency: ExtractionField
    route: ExtractionField
    duration: ExtractionField
    time: ExtractionField
    food_instruction: ExtractionField
    special_instruction: ExtractionField


class PrescriptionLine(Contract):
    line_id: UUID
    ordinal: Annotated[int, Field(strict=True, ge=0)]
    fields: PrescriptionFields


class ExtractionResult(Contract):
    document_kind: Literal["strip", "bottle", "tube", "box", "prescription"]
    medicine: MedicineFields | None
    lines: tuple[PrescriptionLine, ...] = Field(max_length=50)

    @model_validator(mode="after")
    def document_shape(self):
        if self.document_kind == "prescription":
            if self.medicine is not None:
                raise ValueError("Prescription fields belong to individual lines")
        elif self.medicine is None or self.lines:
            raise ValueError("Packaging requires medicine observations and no prescription lines")
        if len({line.line_id for line in self.lines}) != len(self.lines) or len(
            {line.ordinal for line in self.lines}
        ) != len(self.lines):
            raise ValueError("Duplicate prescription line")
        return self


class FieldReview(Contract):
    status: Literal["unreviewed", "confirmed", "corrected", "unresolved"]
    reviewed_value: Text | None

    @model_validator(mode="after")
    def explicit_correction(self):
        if self.status in ("unreviewed", "unresolved") and self.reviewed_value is not None:
            raise ValueError("Unreviewed or unresolved fields cannot have accepted values")
        return self


class SyntheticProvenance(Contract):
    mode: Literal["synthetic"] = "synthetic"
    fixture_id: Annotated[str, Field(pattern=r"^[a-z0-9_-]{1,80}$")]
    source_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class Verification(Contract):
    # Supported clinical facts require future evidence publication contracts.
    status: Literal["unverified", "ambiguous", "unsupported_market"]
    verified_at: None = None

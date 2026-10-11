"""Human transcription review only. No medical acceptance or verification."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from medlm_domain.analysis import Contract, ExtractionResult, FieldReview

Decision = Literal["confirm", "correct", "reject", "unresolved"]
Disposition = Literal["included", "excluded", "unresolved"]


class ReviewTarget(Contract):
    version: int = Field(strict=True, gt=0)
    revision: int = Field(strict=True, gt=0)


class HumanReview(ReviewTarget):
    candidate_set_id: UUID
    candidate_id: None = None
    decision: Decision
    fields: dict[str, FieldReview] = Field(min_length=1, max_length=450)
    line_dispositions: dict[UUID, Disposition]


def observed_fields(extraction: ExtractionResult):
    if extraction.medicine is not None:
        return {key: value.raw_text for key, value in extraction.medicine}
    return {
        f"{line.line_id}.{key}": value.raw_text
        for line in extraction.lines
        for key, value in line.fields
    }


def validate_review(body: HumanReview, extraction: ExtractionResult) -> None:
    expected = observed_fields(extraction)
    if body.fields.keys() != expected.keys():
        raise ValueError("Every observed field requires explicit review")
    line_ids = {line.line_id for line in extraction.lines}
    if body.line_dispositions.keys() != line_ids:
        raise ValueError("Every prescription line requires a disposition")
    included = set()
    for key, field in body.fields.items():
        if field.status == "confirmed" and field.reviewed_value != expected[key]:
            raise ValueError("Confirmation must match literal observed text")
        selected = not line_ids or body.line_dispositions[UUID(key.split(".")[0])] == "included"
        if selected:
            included.add(field.status)
            if line_ids and field.status not in {"confirmed", "corrected"}:
                raise ValueError("Included lines require complete field review")
    if body.decision == "confirm" and included != {"confirmed"}:
        raise ValueError("Confirmation requires confirmed fields")
    if body.decision == "correct" and (
        "corrected" not in included or not included <= {"confirmed", "corrected"}
    ):
        raise ValueError("Correction requires complete field review")


def accepted_values(body: HumanReview, extraction: ExtractionResult) -> dict[str, str | None]:
    # Intermediate/rejected records are history, never accepted instructions.
    if body.decision not in {"confirm", "correct"}:
        return {}
    return {
        key: field.reviewed_value
        for key, field in body.fields.items()
        if extraction.medicine is not None
        or body.line_dispositions[UUID(key.split(".")[0])] == "included"
    }

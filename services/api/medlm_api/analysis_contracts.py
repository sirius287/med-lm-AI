"""Proposed harness DTOs only; intentionally not registered in OpenAPI/routes.

Response metadata is server-owned. Schema validity is not authorization or proof
of fixture admission, review, or evidence. Later services must enforce those gates.
"""

from typing import Annotated, Literal
from uuid import UUID

from medlm_domain.analysis import (
    AnalysisState,
    Contract,
    ExtractionResult,
    FieldReview,
    SyntheticProvenance,
    Verification,
)
from pydantic import Field, model_validator


class AnalysisCreate(Contract):
    upload_ids: tuple[UUID, ...] = Field(min_length=1, max_length=1)
    kind: Literal["medicine", "prescription"]
    country: Literal["IN"]
    locale: Literal["en-IN", "hi-IN", "te-IN"]


class ExtractionRevision(Contract):
    analysis_id: UUID
    revision: Annotated[int, Field(strict=True, gt=0)]
    extraction: ExtractionResult
    provenance: SyntheticProvenance
    verification: Verification
    review_status: Literal["unreviewed", "confirmed", "corrected", "unresolved"]


class ReviewSubmission(Contract):
    revision: Annotated[int, Field(strict=True, gt=0)]
    decision: Literal["confirm", "correct", "reject"]
    fields: dict[str, FieldReview] = Field(min_length=1, max_length=450)

    @model_validator(mode="after")
    def completed_review(self):
        states = {field.status for field in self.fields.values()}
        if self.decision == "confirm" and states != {"confirmed"}:
            raise ValueError("Confirmation requires explicit field review")
        if self.decision == "correct" and (
            "corrected" not in states or not states <= {"confirmed", "corrected"}
        ):
            raise ValueError("Corrections require completed field review")
        return self


class AnalysisStatus(Contract):
    id: UUID
    state: AnalysisState
    result_revision: Annotated[int, Field(strict=True, gt=0)] | None
    reason: (
        Literal["unreadable", "ambiguous", "provider_unavailable", "invalid_output", "expired"]
        | None
    )

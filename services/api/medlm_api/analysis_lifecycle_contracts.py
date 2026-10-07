"""Synthetic harness lifecycle DTOs; no observations or clinical acceptance input."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from medlm_domain.analysis import AnalysisState, Contract
from pydantic import Field


class CreateAnalysis(Contract):
    upload_id: UUID
    document_kind: Literal["strip", "bottle", "tube", "box", "prescription"]
    content_type: Literal["image/jpeg", "image/png", "image/webp"]
    retain_for_review: Literal[True]
    locale: Literal["en-IN", "hi-IN", "te-IN"]


class AnalysisVersion(Contract):
    version: int = Field(strict=True, gt=0)


class LeaseRequest(Contract):
    job_version: int = Field(strict=True, gt=0)


class TransitionRequest(LeaseRequest):
    lease_token: UUID
    fencing_token: int = Field(strict=True, gt=0)
    target: Literal[
        "validating",
        "extracting",
        "retrieving",
        "validating_output",
        "failed",
        "cancelled",
        "needs_input",
    ]


class JobView(Contract):
    id: UUID
    attempt: int
    state: AnalysisState
    version: int
    fencing_token: int
    lease_expires_at: datetime | None


class AnalysisView(Contract):
    id: UUID
    version: int
    availability: Literal["available", "expired", "cancelled", "unavailable"]
    expires_at: datetime
    expired_at: datetime | None
    job: JobView
    result_revision: int | None


class LeaseView(AnalysisView):
    lease_token: UUID

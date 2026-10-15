"""Synthetic saved-text projection. No medical claims or evidence verification."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from medlm_domain.analysis import Contract, ExtractionResult, SyntheticProvenance
from medlm_domain.extraction import ExtractionMetadata
from medlm_domain.review import HumanReview, accepted_values, validate_review

REPORT_KEYS = (
    "medicine_name",
    "generic_name",
    "active_ingredients",
    "strength",
    "dosage_form",
    "manufacturer",
    "common_uses",
    "mechanism_action",
    "common_side_effects",
    "serious_adverse_effects",
    "warnings",
    "contraindications",
    "precautions",
    "drug_interactions",
    "food_beverage_interactions",
    "pregnancy",
    "breastfeeding",
    "pediatric",
    "older_adult",
    "kidney",
    "liver",
    "storage",
    "prescription_otc_status",
    "other_information",
)


class MedicalField(Contract):
    status: Literal["unavailable", "conflicting"]
    value: None = None
    reason: Literal["no_authoritative_source_checked", "conflicting_synthetic_evidence"]
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def state(self):
        if self.status == "unavailable":
            if self.reason != "no_authoritative_source_checked" or self.evidence_refs:
                raise ValueError("Unavailable information has no checked evidence")
        elif self.reason != "conflicting_synthetic_evidence" or len(set(self.evidence_refs)) < 2:
            raise ValueError("Conflicts require distinct synthetic references")
        return self


class SyntheticEvidence(Contract):
    """Server-controlled test alternatives only; never a source catalog record."""

    id: str = Field(min_length=1, max_length=100)
    field_key: str
    alternative: str = Field(min_length=1, max_length=2000)
    provenance: Literal["synthetic_test_not_medical"]
    authoritative: Literal[False] = False


class ReviewedTranscription(Contract):
    id: UUID
    review: HumanReview


class ObservationConflict(Contract):
    field_key: str
    raw_text: str | None
    alternatives: tuple[str, ...]
    ambiguity_reason: str


def _observation_conflicts(observations: ExtractionResult) -> tuple[ObservationConflict, ...]:
    containers = (
        [("", observations.medicine)]
        if observations.medicine is not None
        else [(f"{line.line_id}.", line.fields) for line in observations.lines]
    )
    return tuple(
        ObservationConflict(
            field_key=prefix + key,
            raw_text=value.raw_text,
            alternatives=value.alternatives,
            ambiguity_reason=value.ambiguity_reason,
        )
        for prefix, container in containers
        for key, value in container
        if value.ambiguity_reason is not None
    )


class AnalysisReport(Contract):
    schema_version: Literal[1] = 1
    assembler_version: Literal["synthetic-report-v1"] = "synthetic-report-v1"
    analysis_id: UUID
    analysis_version: int = Field(strict=True, gt=0)
    extraction_revision_id: UUID
    revision: int = Field(strict=True, gt=0)
    country: Literal["IN"]
    locale: Literal["en-IN", "hi-IN", "te-IN"]
    observations: ExtractionResult
    provenance: SyntheticProvenance
    extraction_metadata: ExtractionMetadata
    purpose: Literal["synthetic_test_not_medical"] = "synthetic_test_not_medical"
    review_state: Literal["unreviewed", "confirm", "correct", "reject", "unresolved"]
    review_history: tuple[ReviewedTranscription, ...]
    accepted_transcription: dict[str, str | None]
    observation_conflicts: tuple[ObservationConflict, ...]
    fields: dict[str, MedicalField]
    evidence: tuple[SyntheticEvidence, ...] = ()
    verification_status: Literal["unverified"] = "unverified"
    product_id: None = None
    verified_at: None = None
    source_checked_at: None = None
    image_available: bool
    original_expires_at: datetime
    cancelled: bool
    expired: bool

    @model_validator(mode="after")
    def boundaries(self):
        if set(self.fields) != set(REPORT_KEYS):
            raise ValueError("All report field keys are required")
        refs = {e.id: e for e in self.evidence}
        if len(refs) != len(self.evidence) or any(
            e.field_key not in REPORT_KEYS for e in self.evidence
        ):
            raise ValueError("Invalid synthetic evidence identity")
        for key, field in self.fields.items():
            applicable = {e.id for e in self.evidence if e.field_key == key}
            has_conflict = len({refs[ref].alternative for ref in applicable}) > 1
            if (field.status == "conflicting") != has_conflict:
                raise ValueError("Field state must represent its synthetic evidence conflicts")
            if has_conflict and (
                set(field.evidence_refs) != applicable
                or len(field.evidence_refs) != len(applicable)
            ):
                raise ValueError("Conflict references must include every applicable alternative")
            if any(ref not in refs or refs[ref].field_key != key for ref in field.evidence_refs):
                raise ValueError("Evidence must belong to the exact field")
            if (
                field.status == "conflicting"
                and len({refs[ref].alternative for ref in field.evidence_refs}) < 2
            ):
                raise ValueError("Conflict alternatives must differ")
        # Observation ambiguity stays distinct from medical-information state; it
        # cannot become evidence or disappear merely because a user reviewed it.
        if self.observation_conflicts != _observation_conflicts(self.observations):
            raise ValueError("Conflict summaries must exactly preserve observed ambiguity")
        latest = self.review_history[-1].review if self.review_history else None
        previous, closed, candidate_set = 0, False, None
        for item in self.review_history:
            if item.review.revision != self.revision:
                raise ValueError("Review belongs to a different revision")
            if closed or not previous < item.review.version < self.analysis_version:
                raise ValueError("Review history is stale or closed")
            if candidate_set is not None and candidate_set != item.review.candidate_set_id:
                raise ValueError("Review history must bind one candidate set")
            validate_review(item.review, self.observations)
            previous = item.review.version
            candidate_set = item.review.candidate_set_id
            closed = item.review.decision != "unresolved"
        expected = accepted_values(latest, self.observations) if latest else {}
        if self.accepted_transcription != expected:
            raise ValueError("Transcription requires eligible explicit review")
        if self.review_state != (latest.decision if latest else "unreviewed"):
            raise ValueError("Review state mismatch")
        return self


def assemble_report(*, observations, review_history=(), evidence=(), **metadata):
    """Pure assembly; evidence may only come from a trusted test caller, never HTTP input."""
    fields = {
        key: MedicalField(status="unavailable", reason="no_authoritative_source_checked")
        for key in REPORT_KEYS
    }
    for key in REPORT_KEYS:
        items = [e for e in evidence if e.field_key == key]
        if len({e.alternative for e in items}) > 1:
            fields[key] = MedicalField(
                status="conflicting",
                reason="conflicting_synthetic_evidence",
                evidence_refs=tuple(e.id for e in items),
            )
    conflicts = _observation_conflicts(observations)
    latest = review_history[-1].review if review_history else None
    return AnalysisReport(
        **metadata,
        observations=observations,
        review_history=review_history,
        review_state=latest.decision if latest else "unreviewed",
        accepted_transcription=accepted_values(latest, observations) if latest else {},
        observation_conflicts=conflicts,
        fields=fields,
        evidence=evidence,
    )

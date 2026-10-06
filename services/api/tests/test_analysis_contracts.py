from uuid import uuid4

import pytest
from medlm_api.analysis_contracts import AnalysisCreate, ExtractionRevision, ReviewSubmission
from medlm_domain.analysis import (
    AnalysisState,
    BoundingBox,
    ExtractionField,
    ExtractionResult,
    FieldReview,
    PrescriptionFields,
    SyntheticProvenance,
    Verification,
    transition,
)
from pydantic import ValidationError


def field(**changes):
    return (
        dict(
            raw_text=None,
            normalized_value=None,
            unit=None,
            bounding_box=None,
            ambiguity_reason=None,
            alternatives=[],
            confidence=None,
        )
        | changes
    )


def test_absence_is_explicit_and_never_inferred():
    absent = ExtractionField(**field())
    assert absent.normalized_value is None
    with pytest.raises(ValidationError):
        ExtractionField(raw_text=None)
    with pytest.raises(ValidationError):
        ExtractionField(**field(normalized_value="Synthetic value"))
    with pytest.raises(ValidationError):
        ExtractionField(**field(confirmed=True))


@pytest.mark.parametrize(
    "change",
    [
        {"x": -0.1},
        {"y": 2},
        {"width": 0},
        {"height": float("nan")},
        {"x": 0.9, "width": 0.2},
        {"y": 0.9, "height": 0.2},
        {"x": "0.1"},
        {"extra": True},
    ],
)
def test_invalid_coordinates(change):
    with pytest.raises(ValidationError):
        BoundingBox(**(dict(x=0.1, y=0.1, width=0.2, height=0.2) | change))


def test_strength_does_not_supply_dose():
    values = {name: field() for name in PrescriptionFields.model_fields}
    values["strength"] = field(raw_text=" 0.5 mg ", normalized_value="0.5", unit="mg")
    result = PrescriptionFields(**values)
    assert result.strength.raw_text == " 0.5 mg "
    assert result.dose.normalized_value is None
    del values["dose"]
    with pytest.raises(ValidationError):
        PrescriptionFields(**values)


def test_confidence_cannot_confirm_or_verify():
    observed = ExtractionField(
        **field(
            raw_text="Synthetic label",
            confidence={"source": "fixture", "score": 1.0, "calibration": "uncalibrated"},
        )
    )
    assert observed.confidence.score == 1
    assert "review_status" not in ExtractionField.model_fields
    review = FieldReview(status="confirmed", reviewed_value="Synthetic label")
    verification = Verification(status="unverified")
    assert review.status == "confirmed" and verification.verified_at is None
    with pytest.raises(ValidationError):
        Verification(status="verified_product")
    with pytest.raises(ValidationError):
        SyntheticProvenance(mode="clinical", fixture_id="test", source_sha256="a" * 64)


def test_review_requires_explicit_completed_fields():
    with pytest.raises(ValidationError):
        ReviewSubmission(
            revision=1,
            decision="confirm",
            fields={"medicine": {"status": "unreviewed", "reviewed_value": None}},
        )
    reviewed = ReviewSubmission(
        revision=1,
        decision="confirm",
        fields={"dose": {"status": "confirmed", "reviewed_value": None}},
    )
    assert reviewed.fields["dose"].reviewed_value is None


def test_request_cannot_supply_owner_verification_or_multiple_images():
    body = dict(upload_ids=[uuid4()], kind="medicine", country="IN", locale="en-IN")
    assert len(AnalysisCreate(**body).upload_ids) == 1
    for change in (
        {"user_id": uuid4()},
        {"verified": True},
        {"upload_ids": []},
        {"upload_ids": [uuid4(), uuid4()]},
        {"country": "US"},
    ):
        with pytest.raises(ValidationError):
            AnalysisCreate(**(body | change))


def test_state_machine_rejects_skips_and_terminal_reopening():
    assert transition(AnalysisState.QUEUED, AnalysisState.VALIDATING) == "validating"
    assert transition(AnalysisState.EXTRACTING, AnalysisState.NEEDS_INPUT) == "needs_input"
    with pytest.raises(ValueError):
        transition(AnalysisState.QUEUED, AnalysisState.COMPLETED)
    for terminal in ("completed", "needs_input", "failed", "cancelled"):
        with pytest.raises(ValueError):
            transition(terminal, "queued")


@pytest.mark.parametrize(
    "change",
    [
        {"raw_text": 5},
        {"raw_text": " "},
        {"alternatives": ["Synthetic alternative"]},
        {"confidence": {"source": "fixture", "score": 1.1}},
        {"confidence": {"source": "provider", "score": float("inf")}},
        {"confidence": {"source": "provider", "score": 0.9, "calibration": "calibrated"}},
        {"verification_status": "verified_product"},
    ],
)
def test_invalid_observations_and_confidence(change):
    with pytest.raises(ValidationError):
        ExtractionField(**field(**change))


def test_document_kinds_and_duplicate_prescription_lines():
    packaging = {
        name: field()
        for name in ("medicine", "strength", "ingredients", "dosage_form", "manufacturer")
    }
    for kind in ("strip", "bottle", "tube", "box"):
        assert ExtractionResult(document_kind=kind, medicine=packaging, lines=[]).lines == ()
    line = dict(
        line_id=uuid4(),
        ordinal=0,
        fields={name: field() for name in PrescriptionFields.model_fields},
    )
    assert (
        len(ExtractionResult(document_kind="prescription", medicine=None, lines=[line]).lines) == 1
    )
    for changes in (
        dict(document_kind="prescription", medicine=packaging, lines=[]),
        dict(document_kind="prescription", medicine=None, lines=[line, line]),
        dict(document_kind="strip", medicine=packaging, lines=[line]),
    ):
        with pytest.raises(ValidationError):
            ExtractionResult(**changes)


def test_complete_processing_does_not_imply_verification_or_review():
    stages = ["queued", "validating", "extracting", "retrieving", "validating_output", "completed"]
    for before, after in zip(stages, stages[1:]):
        assert transition(before, after) == after
        assert transition(before, "cancelled") == "cancelled"
        assert transition(before, "failed") == "failed"
    assert Verification(status="ambiguous").verified_at is None
    assert FieldReview(status="unresolved", reviewed_value=None).status == "unresolved"


@pytest.mark.parametrize("review", ["unreviewed", "confirmed", "corrected", "unresolved"])
@pytest.mark.parametrize("verification", ["unverified", "ambiguous", "unsupported_market"])
def test_review_and_verification_remain_independent_in_revision(review, verification):
    result = ExtractionRevision(
        analysis_id=uuid4(),
        revision=1,
        extraction={"document_kind": "prescription", "medicine": None, "lines": []},
        provenance={"fixture_id": "synthetic-empty", "source_sha256": "a" * 64},
        verification={"status": verification},
        review_status=review,
    )
    assert result.provenance.mode == "synthetic"
    assert result.review_status == review
    assert result.verification.status == verification
    assert result.verification.verified_at is None


def test_chunk_one_registers_no_new_routes():
    from medlm_api.config import Settings
    from medlm_api.main import create_app

    app = create_app(Settings(_env_file=None, environment="test"))
    try:
        paths = app.openapi()["paths"]
        for prefix in (
            "/api/v1/analyses",
            "/api/v1/uploads",
            "/api/v1/prescriptions",
            "/api/v1/reports",
        ):
            assert not any(path.startswith(prefix) for path in paths)
    finally:
        app.state.database.close()
        app.state.auth.gateway.close()

"""Reports preserve synthetic transcription without creating medical claims."""

import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from medlm_api.analysis_report import SyntheticReports
from medlm_api.analysis_repository import AnalysisConflict, AnalysisRepository
from medlm_api.analysis_review import HumanReviews
from medlm_api.errors import AppError
from medlm_api.main import create_app
from medlm_api.synthetic_extraction import ExtractRequest
from medlm_api.synthetic_fixtures import controlled_fixture
from medlm_domain.analysis import SyntheticProvenance
from medlm_domain.extraction import ExtractionMetadata
from medlm_domain.report import (
    REPORT_KEYS,
    AnalysisReport,
    ReviewedTranscription,
    SyntheticEvidence,
    assemble_report,
)
from medlm_domain.review import HumanReview, observed_fields
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from test_analysis_lifecycle import path, post
from test_auth_sessions import sign_in
from test_human_review import (
    auth_env as _auth,
)
from test_human_review import (
    extraction_env as _extraction,
)
from test_human_review import (
    isolated_database as _db,
)
from test_human_review import (
    reviewable,
    submit,
)
from test_human_review import (
    reviews as _reviews,
)
from test_human_review import (
    uploads as _uploads,
)
from test_synthetic_extraction import extract, prepared

isolated_database = _db
auth_env = _auth
uploads = _uploads
extraction_env = _extraction
reviews = _reviews


def projection(history=(), evidence=()):
    fixture = controlled_fixture("box", ambiguous=True)
    return assemble_report(
        analysis_id=uuid4(),
        analysis_version=5,
        extraction_revision_id=uuid4(),
        revision=1,
        country="IN",
        locale="en-IN",
        observations=fixture.observations,
        provenance=SyntheticProvenance(fixture_id="test", source_sha256="a" * 64),
        extraction_metadata=ExtractionMetadata(
            provider_id="synthetic",
            model_id="deterministic-v1",
            pipeline_version="synthetic-extraction-v1",
            fixture_revision=1,
            sanitized_sha256="b" * 64,
        ),
        review_history=history,
        evidence=evidence,
        image_available=False,
        original_expires_at=datetime.now(UTC),
        cancelled=False,
        expired=True,
    )


def test_pure_unavailable_and_uncertainty():
    report = projection()
    assert len(report.fields) == 24 and set(report.fields) == set(REPORT_KEYS)
    assert report.review_state == "unreviewed" and report.accepted_transcription == {}
    assert report.observation_conflicts
    assert report.observations == controlled_fixture("box", ambiguous=True).observations
    assert all(
        f.value is None and f.reason == "no_authoritative_source_checked"
        for f in report.fields.values()
    )
    assert report.product_id is report.verified_at is report.source_checked_at is None
    requirements = (Path(__file__).resolve().parents[3] / "REQUIREMENTS.md").read_text(
        encoding="utf-8"
    )
    key_line = next(
        line for line in requirements.splitlines() if line.startswith("Required schema keys:")
    )
    assert set(re.findall(r"`([^`]+)`", key_line)) == set(REPORT_KEYS)


@pytest.mark.parametrize(
    "change",
    ["missing", "extra_key", "extra", "value", "verified", "accepted", "evidence", "conflict"],
)
def test_contract_rejects_unsafe_payload(change):
    data = projection().model_dump()
    if change == "missing":
        data["fields"].pop("strength")
    elif change == "extra_key":
        data["fields"]["dose_advice"] = data["fields"]["strength"]
    elif change == "extra":
        data["clinical_safety"] = True
    elif change == "value":
        data["fields"]["strength"]["value"] = "invented"
    elif change == "verified":
        data["verification_status"] = "verified"
    elif change == "accepted":
        data["accepted_transcription"] = {"medicine": "invented"}
    elif change == "evidence":
        data["fields"]["strength"]["evidence_refs"] = ["unknown"]
    else:
        data["fields"]["strength"].update(
            status="conflicting", reason="conflicting_synthetic_evidence"
        )
    with pytest.raises(ValidationError):
        AnalysisReport.model_validate(data)


def test_synthetic_conflict_never_selects_a_medical_value():
    evidence = tuple(
        SyntheticEvidence(
            id=str(i),
            field_key="medicine_name",
            alternative=f"TEST {i}",
            provenance="synthetic_test_not_medical",
        )
        for i in range(2)
    )
    report = projection(evidence=evidence)
    assert report.fields["medicine_name"].status == "conflicting"
    assert report.fields["medicine_name"].value is None
    assert report.evidence == evidence and report.verification_status == "unverified"
    with pytest.raises(ValidationError):
        SyntheticEvidence.model_validate(evidence[0].model_dump() | {"authoritative": True})


@pytest.mark.parametrize("decision", ["confirm", "correct", "reject", "unresolved"])
def test_review_eligibility_and_corrections(decision):
    observation = controlled_fixture("box", ambiguous=True).observations
    fields = {
        k: {"status": "confirmed", "reviewed_value": v}
        for k, v in observed_fields(observation).items()
    }
    if decision == "correct":
        fields["medicine"] = {"status": "corrected", "reviewed_value": "  TEST CORRECTION  "}
    body = HumanReview(
        version=3,
        revision=1,
        candidate_set_id=uuid4(),
        decision=decision,
        fields=fields,
        line_dispositions={},
    )
    report = projection((ReviewedTranscription(id=uuid4(), review=body),))
    assert report.observations == observation
    assert bool(report.accepted_transcription) == (decision in {"confirm", "correct"})
    if decision == "correct":
        assert report.accepted_transcription["medicine"] == "  TEST CORRECTION  "
    assert all(f.status == "unavailable" for f in report.fields.values())
    with pytest.raises(ValueError):
        projection(
            (ReviewedTranscription(id=uuid4(), review=body.model_copy(update={"revision": 2})),)
        )


@pytest.fixture
def reports(reviews):
    old, runner, _, engine, provider, review_service = reviews
    service = SyntheticReports(runner.lifecycle)
    app = create_app(
        old.app.state.settings,
        provider,
        synthetic_uploads=runner.lifecycle.uploads,
        synthetic_analyses=runner.lifecycle,
        synthetic_reports=service,
    )
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer synthetic-access"
        yield client, service


def get_report(client, a, revision=1):
    return client.get(path(a) + "/report", params={"revision": revision})


def test_unreviewed_current_snapshot_and_default_route(reviews, reports):
    a, body, fixture = prepared(reviews[:5])
    assert extract(reviews[0], a, body).status_code == 200
    response = get_report(reports[0], a)
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["review_state"] == "unreviewed" and report["review_history"] == []
    assert report["observations"] == fixture.observations.model_dump(mode="json")
    assert len(report["fields"]) == 24 and report["evidence"] == []
    assert get_report(reports[0], a, 2).status_code == 409
    # Existing extraction/review harness does not automatically expose reports.
    assert get_report(reviews[0], a).status_code == 404
    assert not any("/report" in p for p in create_app().openapi()["paths"])
    with pytest.raises(ValueError):
        create_app(synthetic_reports=reports[1])
    assert (
        post(reviews[0], path(a) + "/jobs", {"version": report["analysis_version"]}).status_code
        == 201
    )
    assert get_report(reports[0], a).status_code == 409


def test_prescription_dispositions_and_deleted_image(reviews, reports, uploads):
    a, _, body, fixture = reviewable(reviews, 4)
    lines = [str(line.line_id) for line in fixture.observations.lines]
    body["line_dispositions"][lines[1]] = "excluded"
    assert submit(reviews, a, body).status_code == 201
    before = get_report(reports[0], a).json()
    assert all(k.startswith(lines[0]) for k in before["accepted_transcription"])
    assert before["review_history"][0]["review"]["line_dispositions"][lines[1]] == "excluded"
    assert uploads[2].run("deletion_worker")["outcome"] == "ok"
    assert get_report(reports[0], a).json() == before
    assert before["observations"] == fixture.observations.model_dump(mode="json")
    assert before["verification_status"] == "unverified" and not before["image_available"]


@pytest.mark.parametrize("state", ["cancelled", "expired", "erased"])
def test_saved_text_retention_no_writes(reviews, reports, state):
    if state == "expired":
        reviews[1].lifecycle.uploads.ttl = 3
    a, context, _, _ = reviewable(reviews)
    client, service = reports
    if state == "cancelled":
        assert (
            post(reviews[0], path(a) + "/cancel", {"version": context["version"]}).status_code
            == 200
        )
    elif state == "expired":
        with reviews[3].connect() as conn:
            conn.execute(text("SELECT pg_sleep(3.1)"))
    else:
        principal = client.app.state.auth.native("synthetic-access")
        with service.lifecycle.owned(client.app.state.database, principal) as conn:
            AnalysisRepository(conn, principal.user_id).erase(UUID(a["id"]), context["version"])
    engine = reviews[3]

    def saved():
        with engine.connect() as conn:
            return [
                conn.execute(text(f"SELECT to_jsonb(t) FROM medlm.{table} t ORDER BY id"))
                .scalars()
                .all()
                for table in ("medicine_analyses", "analysis_reviews", "upload_deletion_jobs")
            ]

    before = saved()
    response = get_report(client, a)
    assert saved() == before
    if state == "erased":
        assert response.status_code == 404
    else:
        assert response.status_code == 200, response.text
        assert response.json()[state] and not response.json()["image_available"]


@pytest.mark.parametrize("state", ["foreign", "logout", "disabled", "anonymous", "cookie"])
def test_authentication_and_owner_boundary(reviews, reports, state):
    a, _, _, _ = reviewable(reviews)
    client, _ = reports
    provider = reviews[4]
    if state == "foreign":
        provider.user = uuid4()
        expected = 404
    elif state == "logout":
        assert client.delete("/api/v1/auth/session").status_code == 204
        expected = 401
    elif state == "disabled":
        with reviews[3].begin() as conn:
            conn.execute(text("UPDATE medlm.users SET disabled_at=now()"))
        expected = 401
    elif state == "anonymous":
        client.headers.pop("Authorization")
        expected = 401
    else:
        client.headers.pop("Authorization")
        cookie, _, _ = sign_in(client.app)
        client.cookies.set("medlm_session", cookie)
        expected = 200  # GET performs no mutation and needs no CSRF token.
    assert get_report(client, a).status_code == expected


@pytest.mark.parametrize(
    "change", ["missing_field", "wrong_literal", "stale_version", "after_final", "foreign_set"]
)
def test_ineligible_review_history_fails_closed(change):
    observation = controlled_fixture("box", ambiguous=True).observations
    body = HumanReview(
        version=2,
        revision=1,
        candidate_set_id=uuid4(),
        decision="confirm",
        fields={
            k: {"status": "confirmed", "reviewed_value": v}
            for k, v in observed_fields(observation).items()
        },
        line_dispositions={},
    )
    data = body.model_dump()
    if change == "missing_field":
        data["fields"].pop("strength")
    elif change == "wrong_literal":
        data["fields"]["medicine"]["reviewed_value"] = "invented"
    elif change == "stale_version":
        data["version"] = 5
    history = (ReviewedTranscription(id=uuid4(), review=HumanReview.model_validate(data)),)
    if change in {"after_final", "foreign_set"}:
        if change == "foreign_set":
            history = (
                ReviewedTranscription(
                    id=uuid4(), review=body.model_copy(update={"decision": "unresolved"})
                ),
            )
        history += (
            ReviewedTranscription(
                id=uuid4(),
                review=body.model_copy(
                    update={
                        "version": 3,
                        "candidate_set_id": uuid4()
                        if change == "foreign_set"
                        else body.candidate_set_id,
                    }
                ),
            ),
        )
    with pytest.raises(ValueError):
        projection(history)


def test_intermediate_and_final_correction_snapshot(reviews, reports):
    a, _, body, fixture = reviewable(reviews)
    body["decision"] = "unresolved"
    receipt = submit(reviews, a, body).json()
    intermediate = get_report(reports[0], a).json()
    assert (
        intermediate["review_state"] == "unresolved"
        and intermediate["accepted_transcription"] == {}
    )
    body["version"] = receipt["version"]
    body["decision"] = "correct"
    body["fields"]["medicine"] = {"status": "corrected", "reviewed_value": "  TEST CORRECTION  "}
    assert submit(reviews, a, body).status_code == 201
    final = get_report(reports[0], a).json()
    assert len(final["review_history"]) == 2
    assert final["accepted_transcription"]["medicine"] == "  TEST CORRECTION  "
    assert final["observations"] == fixture.observations.model_dump(mode="json")
    assert all(f["value"] is None for f in final["fields"].values())


def test_report_snapshot_serializes_with_review(reviews, reports, monkeypatch):
    import medlm_api.analysis_report as module

    a, context, body, _ = reviewable(reviews)
    assembling, release, submitting = Event(), Event(), Event()
    original = module.assemble_report

    def paused(**kwargs):
        assembling.set()
        assert release.wait(10)
        return original(**kwargs)

    def review():
        submitting.set()
        return submit(reviews, a, body)

    monkeypatch.setattr(module, "assemble_report", paused)
    with ThreadPoolExecutor(max_workers=2) as pool:
        reading = pool.submit(get_report, reports[0], a)
        try:
            assert assembling.wait(10)
            writing = pool.submit(review)
            assert submitting.wait(10)
            assert not writing.done()
        finally:
            release.set()
        response = reading.result(timeout=10)
        assert writing.result(timeout=10).status_code == 201
    assert response.status_code == 200
    assert response.json()["analysis_version"] == context["version"]
    assert response.json()["review_state"] == "unreviewed"
    assert get_report(reports[0], a).json()["review_state"] == "confirm"


def test_malformed_persisted_observations_return_safe_conflict(reviews, reports):
    client, runner, _, engine, _, _ = reviews
    a, body, fixture = prepared(reviews[:5])
    principal = client.app.state.auth.native("synthetic-access")
    lease = ExtractRequest.model_validate(body)
    # Test-only persistence input simulates malformed legacy observations without
    # disabling constraints/triggers or changing any immutable existing revision.
    malformed = fixture.observations.model_copy(update={"medicine": None})
    with runner.lifecycle.owned(client.app.state.database, principal) as conn:
        for state in ("validating", "extracting", "retrieving", "validating_output"):
            runner.stage(conn, UUID(a["job"]["id"]), lease, state)
        AnalysisRepository(conn, principal.user_id).publish(
            UUID(a["id"]),
            UUID(a["job"]["id"]),
            a["version"],
            malformed,
            SyntheticProvenance(
                fixture_id=fixture.descriptor.fixture_id,
                source_sha256=fixture.descriptor.original_sha256,
            ),
            lease_token=lease.lease_token,
            fencing_token=lease.fencing_token,
            session_id=principal.session_id,
            metadata=ExtractionMetadata(
                **runner.adapter.identity.model_dump(),
                fixture_revision=fixture.descriptor.fixture_revision,
                sanitized_sha256=fixture.descriptor.sanitized_sha256,
            ),
        )
    with engine.connect() as conn:
        assert (
            conn.scalar(text("SELECT observations FROM medlm.extraction_revisions"))["medicine"]
            is None
        )
    response = get_report(reports[0], a)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "report_unavailable"
    assert response.json()["error"]["message"] == "Saved report input is unavailable."
    assert "validation" not in response.text.lower()


@pytest.mark.parametrize(
    "error",
    [
        AppError(401, "invalid_session", "Sign in again."),
        AppError(404, "not_found", "Unavailable."),
        AppError(409, "stale_revision", "Stale."),
        SQLAlchemyError("database failure"),
        RuntimeError("programming failure"),
        ValueError("unrelated failure"),
    ],
)
def test_target_errors_are_not_reclassified(monkeypatch, error):
    class Lifecycle:
        def owned(self, db, principal):
            return nullcontext(object())

    def failing_target(*args, **kwargs):
        raise error

    monkeypatch.setattr(HumanReviews, "target", failing_target)
    with pytest.raises(type(error)) as caught:
        SyntheticReports(Lifecycle()).get(None, None, uuid4(), 1)
    assert caught.value is error


@pytest.mark.parametrize(
    "change", ["unavailable", "missing_refs", "omitted_ref", "foreign_ref", "same_alternative"]
)
def test_conflict_state_requires_complete_consistent_evidence(change):
    evidence = tuple(
        SyntheticEvidence(
            id=str(i),
            field_key="medicine_name",
            alternative=f"TEST {i}",
            provenance="synthetic_test_not_medical",
        )
        for i in range(3)
    )
    report = projection(evidence=evidence)
    assert AnalysisReport.model_validate(report.model_dump()) == report
    data = report.model_dump()
    field = data["fields"]["medicine_name"]
    if change == "unavailable":
        field.update(
            status="unavailable", reason="no_authoritative_source_checked", evidence_refs=()
        )
    elif change == "missing_refs":
        field["evidence_refs"] = ()
    elif change == "omitted_ref":
        field["evidence_refs"] = ("0", "1")
    elif change == "foreign_ref":
        data["evidence"][0]["field_key"] = "strength"
    else:
        for item in data["evidence"]:
            item["alternative"] = "SAME TEST"
    with pytest.raises(ValidationError):
        AnalysisReport.model_validate(data)


@pytest.mark.parametrize(
    "change", ["missing", "duplicate", "field", "literal", "alternatives", "reason", "no_ambiguity"]
)
def test_observation_conflict_summaries_match_original(change):
    report = projection()
    assert AnalysisReport.model_validate(report.model_dump()) == report
    data = report.model_dump()
    summary = data["observation_conflicts"][0]
    if change == "missing":
        data["observation_conflicts"] = ()
    elif change == "duplicate":
        data["observation_conflicts"] += (dict(summary),)
    elif change == "no_ambiguity":
        original = data["observations"]["medicine"]["medicine"]
        original.update(ambiguity_reason=None, alternatives=())
    else:
        key = {
            "field": "field_key",
            "literal": "raw_text",
            "alternatives": "alternatives",
            "reason": "ambiguity_reason",
        }[change]
        summary[key] = ("OTHER TEST",) if change == "alternatives" else "OTHER TEST"
    with pytest.raises(ValidationError):
        AnalysisReport.model_validate(data)


def test_final_transcription_remains_unverified_after_image_expiry(reviews, reports):
    reviews[1].lifecycle.uploads.ttl = 3
    a, _, body, fixture = reviewable(reviews)
    assert submit(reviews, a, body).status_code == 201
    with reviews[3].connect() as conn:
        conn.execute(text("SELECT pg_sleep(3.1)"))
    response = get_report(reports[0], a)
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["expired"] and not report["image_available"]
    assert report["review_state"] == "confirm"
    assert report["accepted_transcription"] == observed_fields(fixture.observations)
    assert report["verification_status"] == "unverified" and report["verified_at"] is None


def test_saved_report_survives_verified_upload_metadata_removal(reviews, reports, uploads):
    a, _, body, fixture = reviewable(reviews)
    assert submit(reviews, a, body).status_code == 201
    assert uploads[2].run("deletion_worker")["outcome"] == "ok"
    before = get_report(reports[0], a).json()
    # Simulate eventual inventory erasure only after real object deletion, using
    # the existing restricted maintenance role and its normal FK/receipt guards.
    with uploads[2].db.transaction() as conn:
        assert (
            conn.scalar(text("SELECT count(*) FROM medlm.upload_objects WHERE purged_at IS NULL"))
            == 0
        )
        assert conn.scalar(text("SELECT count(*) FROM medlm.upload_deletion_receipts")) > 0
        assert conn.execute(text("DELETE FROM medlm.uploads WHERE status='deleted'")).rowcount == 1
    response = get_report(reports[0], a)
    assert response.status_code == 200, response.text
    assert response.json() == before
    assert response.json()["observations"] == fixture.observations.model_dump(mode="json")


def test_report_snapshot_serializes_with_analysis_erasure(reviews, reports, monkeypatch):
    import medlm_api.analysis_report as module

    a, context, _, _ = reviewable(reviews)
    service = reports[1]
    principal = reports[0].app.state.auth.native("synthetic-access")
    assembling, release, erasing = Event(), Event(), Event()
    original = module.assemble_report

    def paused(**kwargs):
        assembling.set()
        assert release.wait(10)
        return original(**kwargs)

    def erase():
        erasing.set()
        with service.lifecycle.owned(reports[0].app.state.database, principal) as conn:
            AnalysisRepository(conn, principal.user_id).erase(UUID(a["id"]), context["version"])

    monkeypatch.setattr(module, "assemble_report", paused)
    with ThreadPoolExecutor(max_workers=2) as pool:
        reading = pool.submit(get_report, reports[0], a)
        try:
            assert assembling.wait(10)
            removal = pool.submit(erase)
            assert erasing.wait(10)
            assert not removal.done()
        finally:
            release.set()
        assert reading.result(timeout=10).status_code == 200
        removal.result(timeout=10)
    assert get_report(reports[0], a).status_code == 404


def test_analysis_erasure_clears_owned_replay_bodies_only(reviews, reports):
    a, _, body, _ = reviewable(reviews)
    final = submit(reviews, a, body).json()
    other, _, _, _ = reviewable(reviews, 2)
    client, service = reports
    principal = client.app.state.auth.native("synthetic-access")

    def cached(identity):
        with reviews[3].connect() as conn:
            return conn.execute(
                text("""SELECT operation,key,encrypted_response,invalidated,expires_at
                FROM medlm.idempotency_records WHERE user_id=:u AND resource_id=:id ORDER BY operation,key"""),
                {"u": principal.user_id, "id": UUID(identity["id"])},
            ).all()

    before, unrelated = cached(a), cached(other)
    assert before and all(row.encrypted_response and not row.invalidated for row in before)
    cipher = Fernet(service.lifecycle.key.get_secret_value().encode())
    assert any(b'"extraction"' in cipher.decrypt(row.encrypted_response.encode()) for row in before)
    with pytest.raises(AnalysisConflict):
        with service.lifecycle.owned(client.app.state.database, principal) as conn:
            AnalysisRepository(conn, principal.user_id).erase(UUID(a["id"]), final["version"] - 1)
    assert cached(a) == before
    with service.lifecycle.owned(client.app.state.database, principal) as conn:
        AnalysisRepository(conn, principal.user_id).erase(UUID(a["id"]), final["version"])
    after = cached(a)
    assert len(after) == len(before)
    assert all(row.encrypted_response == "" and row.invalidated for row in after)
    assert [(row.operation, row.key, row.expires_at) for row in after] == [
        (row.operation, row.key, row.expires_at) for row in before
    ]
    assert cached(other) == unrelated
    assert get_report(client, a).status_code == 404

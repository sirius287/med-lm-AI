"""Synthetic transcription review; no medical facts, providers or medication writes."""

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from alembic import command
from fastapi.testclient import TestClient
from medlm_api.analysis_repository import AnalysisRepository
from medlm_api.analysis_review import HumanReviews
from medlm_api.main import create_app
from medlm_domain.review import HumanReview, accepted_values, observed_fields, validate_review
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_analysis_lifecycle import path, post
from test_auth_sessions import sign_in
from test_synthetic_extraction import auth_env as _auth_fixture
from test_synthetic_extraction import extract, prepared
from test_synthetic_extraction import extraction_env as _extraction_fixture
from test_synthetic_extraction import isolated_database as _db_fixture
from test_synthetic_extraction import uploads as _uploads_fixture
from test_upload_schema import snapshot

isolated_database = _db_fixture
auth_env = _auth_fixture
uploads = _uploads_fixture
extraction_env = _extraction_fixture
HEAD = "0009_human_review"


@pytest.fixture
def reviews(extraction_env):
    old, runner, fixtures, engine, provider = extraction_env
    service = HumanReviews(runner.lifecycle)
    app = create_app(
        old.app.state.settings,
        provider,
        synthetic_uploads=runner.lifecycle.uploads,
        synthetic_analyses=runner.lifecycle,
        synthetic_extraction=runner,
        synthetic_reviews=service,
    )
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer synthetic-access"
        yield client, runner, fixtures, engine, provider, service


def reviewable(env, index=3):
    a, body, fixture = prepared(env[:5], index)
    result = extract(env[0], a, body)
    assert result.status_code == 200, result.text
    status = result.json()["status"]
    target = {"version": status["version"], "revision": status["result_revision"]}
    response = post(env[0], path(a) + "/review-context", target)
    assert response.status_code == 200, response.text
    context = response.json()
    fields = {
        key: {"status": "confirmed", "reviewed_value": value}
        for key, value in observed_fields(fixture.observations).items()
    }
    submission = target | {
        "candidate_set_id": context["candidate_set_id"],
        "decision": "confirm",
        "fields": fields,
        "line_dispositions": {str(line.line_id): "included" for line in fixture.observations.lines},
    }
    return a, context, submission, fixture


def submit(env, a, body, key=None):
    return post(env[0], path(a) + "/reviews", body, key)


@pytest.mark.parametrize("index", [0, 1, 2, 3, 4])
def test_final_review_immutable_and_deleted_receipt_replay(reviews, uploads, index):
    client, _, _, engine, _, _ = reviews
    a, context, body, fixture = reviewable(reviews, index)
    assert context["candidates"] == [] and not context["closed"]
    key = uuid4()
    response = submit(reviews, a, body, key)
    assert response.status_code == 201, response.text
    receipt = response.json()
    assert receipt["final"] and receipt["decision"] == "confirm"
    assert receipt["verification"] == {"status": "unverified", "verified_at": None}
    assert receipt["version"] == body["version"] + 1
    assert submit(reviews, a, body, key).json() == receipt
    assert uploads[2].run("deletion_worker")["outcome"] == "ok"
    assert submit(reviews, a, body, key).json() == receipt
    # Persistent request binding survives expiry/removal of the 24-hour encrypted cache.
    with engine.begin() as c:
        c.execute(text("DELETE FROM medlm.idempotency_records"))
    assert submit(reviews, a, body, key).json() == receipt
    current = client.get(path(a) + "/review-context").json()
    assert current["closed"] and not current["image_available"]
    assert current["extraction"] == fixture.observations.model_dump(mode="json")
    assert submit(reviews, a, body | {"decision": "reject"}, key).status_code == 409
    assert submit(reviews, a, body).status_code == 409
    assert post(client, path(a) + "/jobs", {"version": receipt["version"]}).status_code in (
        409,
        410,
    )
    with engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM medlm.identity_candidates")) == 0
        assert c.scalar(text("SELECT count(*) FROM medlm.analysis_reviews")) == 1
        assert c.scalar(text("SELECT count(*) FROM medlm.upload_deletion_receipts")) > 0
        assert c.scalar(text("SELECT count(*) FROM medlm.medications")) == 0
    with pytest.raises(DBAPIError, match="immutable"):
        with engine.begin() as c:
            c.execute(text("UPDATE medlm.analysis_reviews SET decision='reject'"))


@pytest.mark.parametrize("decision", ["correct", "reject", "unresolved"])
def test_decisions_and_separate_corrections(reviews, decision):
    client, _, _, engine, _, _ = reviews
    a, _, body, fixture = reviewable(reviews)
    body["decision"] = decision
    if decision == "correct":
        body["fields"]["medicine"] = {"status": "corrected", "reviewed_value": None}
    if decision == "unresolved":
        body["fields"]["medicine"] = {"status": "unresolved", "reviewed_value": None}
    response = submit(reviews, a, body)
    assert response.status_code == 201, response.text
    receipt = response.json()
    if decision in ("unresolved", "reject"):
        assert receipt["accepted_values"] == {}
    else:
        assert receipt["accepted_values"]["medicine"] is None
    with engine.connect() as c:
        assert c.scalar(
            text("SELECT observations FROM medlm.extraction_revisions")
        ) == fixture.observations.model_dump(mode="json")
        assert c.scalar(text("SELECT verification FROM medlm.extraction_revisions")) == "unverified"
        assert c.scalar(text("SELECT count(*) FROM medlm.upload_deletion_jobs")) == (
            0 if decision == "unresolved" else 1
        )
    if decision == "unresolved":
        context = client.get(path(a) + "/review-context").json()
        assert not context["closed"] and context["image_available"]
        final = body | {"version": receipt["version"], "decision": "reject"}
        assert submit(reviews, a, final).status_code == 201


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "extra",
        "mismatch",
        "whitespace",
        "null",
        "foreign_set",
        "candidate",
        "extra_metadata",
    ],
)
def test_invalid_review_is_noop(reviews, change):
    _, _, _, engine, _, _ = reviews
    a, _, body, _ = reviewable(reviews)
    if change == "missing":
        body["fields"].pop("strength")
    elif change == "extra":
        body["fields"]["dose"] = {"status": "confirmed", "reviewed_value": None}
    elif change in ("mismatch", "whitespace"):
        body["fields"]["medicine"]["reviewed_value"] += (
            " " if change == "whitespace" else " changed"
        )
    elif change == "null":
        body["fields"]["strength"]["reviewed_value"] = "invented"
    elif change == "foreign_set":
        body["candidate_set_id"] = str(uuid4())
    elif change == "candidate":
        body["candidate_id"] = str(uuid4())
    else:
        body["verified_at"] = "anything"
    assert submit(reviews, a, body).status_code in (409, 422)
    with engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM medlm.analysis_reviews")) == 0
        assert c.scalar(text("SELECT count(*) FROM medlm.upload_deletion_jobs")) == 0


def test_prescription_intermediate_and_mixed_dispositions(reviews):
    client, _, _, engine, _, _ = reviews
    a, _, body, fixture = reviewable(reviews, 4)
    ids = [str(line.line_id) for line in fixture.observations.lines]
    body["decision"] = "unresolved"
    body["line_dispositions"][ids[1]] = "unresolved"
    for k in body["fields"]:
        if k.startswith(ids[1]):
            body["fields"][k] = {"status": "unresolved", "reviewed_value": None}
    response = submit(reviews, a, body)
    assert response.status_code == 201, response.text
    assert response.json()["accepted_values"] == {}
    with engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM medlm.analysis_prescription_confirmations")) == 0
    body["version"] = response.json()["version"]
    body["decision"] = "confirm"
    body["line_dispositions"][ids[1]] = "excluded"
    response = submit(reviews, a, body)
    assert response.status_code == 201, response.text
    assert all(k.startswith(ids[0]) for k in response.json()["accepted_values"])
    with engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM medlm.analysis_prescription_confirmations")) == 1
        assert c.execute(
            text(
                "SELECT disposition FROM medlm.analysis_prescription_confirmation_lines ORDER BY disposition"
            )
        ).scalars().all() == ["excluded", "included"]
        assert c.execute(
            text("SELECT source_line_id FROM medlm.analysis_prescription_lines ORDER BY ordinal")
        ).scalars().all() == [UUID(x) for x in ids]
    with pytest.raises(DBAPIError, match="immutable"):
        with engine.begin() as c:
            c.execute(
                text("UPDATE medlm.analysis_prescription_confirmations SET reviewed_fields='{}'")
            )
    assert client.get(path(a) + "/review-context").json()["closed"]


@pytest.mark.parametrize(
    "change", ["missing_line", "foreign_line", "missing_field", "unreviewed_included"]
)
def test_prescription_coverage(reviews, change):
    a, _, body, _ = reviewable(reviews, 4)
    first = next(iter(body["line_dispositions"]))
    if change == "missing_line":
        body["line_dispositions"].pop(first)
    elif change == "foreign_line":
        body["line_dispositions"][str(uuid4())] = "excluded"
    elif change == "missing_field":
        body["fields"].pop(first + ".dose")
    else:
        body["fields"][first + ".dose"] = {"status": "unreviewed", "reviewed_value": None}
    assert submit(reviews, a, body).status_code == 422


def test_stale_revision_and_replay_rejected(reviews):
    client, _, _, _, _, _ = reviews
    a, _, body, _ = reviewable(reviews)
    body["decision"] = "unresolved"
    key = uuid4()
    response = submit(reviews, a, body, key)
    assert response.status_code == 201
    assert (
        post(client, path(a) + "/jobs", {"version": response.json()["version"]}).status_code == 201
    )
    assert submit(reviews, a, body, key).status_code == 409
    assert submit(reviews, a, body).status_code == 409


def test_concurrent_final_reviews_and_identical_replay(reviews):
    _, _, _, engine, _, _ = reviews
    a, _, body, _ = reviewable(reviews)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: submit(reviews, a, body), range(2)))
    assert sorted(r.status_code for r in results) == [201, 409]
    with engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM medlm.analysis_reviews")) == 1


def test_concurrent_identical_review_returns_same_receipt(reviews):
    a, _, body, _ = reviewable(reviews)
    key = uuid4()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: submit(reviews, a, body, key), range(2)))
    assert [r.status_code for r in results] == [201, 201]
    assert results[0].json() == results[1].json()


def test_intermediate_version_conflict_and_original_deadline(reviews):
    client, _, _, _, _, _ = reviews
    a, context, body, _ = reviewable(reviews)
    body["decision"] = "unresolved"
    key = uuid4()
    first = submit(reviews, a, body, key)
    assert first.status_code == 201
    assert submit(reviews, a, body).status_code == 409
    assert submit(reviews, a, body, key).json() == first.json()
    current = client.get(path(a) + "/review-context").json()
    assert current["expires_at"] == context["expires_at"]
    assert current["version"] == context["version"] + 1


@pytest.mark.parametrize("missing", ["version", "deletion"])
def test_database_requires_atomic_review_completion(reviews, missing):
    client, _, _, engine, _, service = reviews
    a, _, body, _ = reviewable(reviews)
    principal = client.app.state.auth.native("synthetic-access")
    with pytest.raises(DBAPIError, match="consume analysis version|queue deletion"):
        with service.lifecycle.owned(client.app.state.database, principal) as c:
            revision = c.scalar(
                text("SELECT current_revision_id FROM medlm.medicine_analyses WHERE id=:id"),
                {"id": UUID(a["id"])},
            )
            AnalysisRepository(c, principal.user_id).append_review(
                UUID(a["id"]), revision, HumanReview.model_validate(body), uuid4(), "a" * 64
            )
            if missing == "deletion":
                c.execute(
                    text("UPDATE medlm.medicine_analyses SET version=version+1 WHERE id=:id"),
                    {"id": UUID(a["id"])},
                )
    with engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM medlm.analysis_reviews")) == 0


def test_cross_user_candidate_set_rejected(reviews):
    client, _, _, _, provider, _ = reviews
    a, _, body, _ = reviewable(reviews)
    owner = provider.user
    provider.user = uuid4()
    _, other, _, _ = reviewable(reviews)
    provider.user = owner
    body["candidate_set_id"] = other["candidate_set_id"]
    assert submit(reviews, a, body).status_code == 409


def test_legacy_extraction_survives_review_migration_rollback(reviews, isolated_database):
    client, _, _, engine, _, _ = reviews
    a, lease_body, _ = prepared(reviews[:5])
    assert extract(client, a, lease_body).status_code == 200
    tables = ("medicine_analyses", "analysis_jobs", "extraction_revisions")

    def rows():
        with engine.connect() as c:
            return [
                c.execute(text("SELECT to_jsonb(t) FROM medlm." + table + " t")).scalars().all()
                for table in tables
            ]

    before = rows()
    command.downgrade(isolated_database[1], "0008_synthetic_extraction")
    assert rows() == before
    command.upgrade(isolated_database[1], HEAD)
    assert rows() == before


@pytest.mark.parametrize("state", ["expiry", "cancel", "logout", "disabled_account"])
def test_unavailable_review(reviews, state):
    client, runner, _, engine, _, _ = reviews
    if state == "expiry":
        runner.lifecycle.uploads.ttl = 3
    a, context, body, _ = reviewable(reviews)
    if state == "expiry":
        with engine.connect() as c:
            c.execute(text("SELECT pg_sleep(3.1)"))
    elif state == "cancel":
        assert post(client, path(a) + "/cancel", {"version": context["version"]}).status_code == 200
    elif state == "disabled_account":
        with engine.begin() as c:
            c.execute(text("UPDATE medlm.users SET disabled_at=now()"))
    else:
        assert client.delete("/api/v1/auth/session").status_code == 204
    assert submit(reviews, a, body).status_code in (401, 403, 410)
    with engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM medlm.analysis_reviews")) == 0


def test_ownership_session_csrf_and_rls(reviews):
    client, _, _, engine, provider, _ = reviews
    a, _, body, _ = reviewable(reviews)
    user = provider.user
    provider.user = uuid4()
    assert submit(reviews, a, body).status_code == 404
    assert client.get(path(a) + "/review-context").status_code == 404
    with engine.begin() as c:
        c.execute(text("SET LOCAL ROLE medlm_runtime"))
        c.execute(text("SELECT set_config('app.user_id',:u,true)"), {"u": str(provider.user)})
        assert c.scalar(text("SELECT count(*) FROM medlm.identity_candidate_sets")) == 0
    provider.user = user
    client.headers.pop("Authorization")
    assert submit(reviews, a, body).status_code == 401
    cookie, csrf, _ = sign_in(client.app)
    client.cookies.set("medlm_session", cookie)
    headers = {"Origin": client.app.state.settings.cors_origins[0], "Idempotency-Key": str(uuid4())}
    assert client.post(path(a) + "/reviews", json=body, headers=headers).status_code == 403
    assert (
        client.post(
            path(a) + "/reviews", json=body, headers=headers | {"X-CSRF-Token": csrf}
        ).status_code
        == 201
    )


def test_literal_null_and_uncertainty_semantics():
    from medlm_api.synthetic_fixtures import controlled_fixture

    result = controlled_fixture("box", ambiguous=True).observations
    payload = result.model_dump()
    payload["medicine"]["medicine"]["raw_text"] = "  TEST ITEM A  "
    result = type(result).model_validate(payload)
    body = HumanReview(
        version=1,
        revision=1,
        candidate_set_id=uuid4(),
        decision="confirm",
        fields={
            k: {"status": "confirmed", "reviewed_value": v}
            for k, v in observed_fields(result).items()
        },
        line_dispositions={},
    )
    validate_review(body, result)
    assert accepted_values(body, result)["medicine"] == "  TEST ITEM A  "
    assert result.medicine.medicine.ambiguity_reason == "Synthetic ambiguity"
    assert accepted_values(body, result)["strength"] is None


def test_migration_roundtrip(isolated_database):
    engine, cfg = isolated_database
    command.upgrade(cfg, "0008_synthetic_extraction")
    with engine.connect() as c:
        before = snapshot(c)
    command.upgrade(cfg, HEAD)
    command.downgrade(cfg, "0008_synthetic_extraction")
    with engine.connect() as c:
        assert snapshot(c) == before
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    with engine.connect() as c:
        assert c.scalar(text("SELECT version_num FROM alembic_version")) == HEAD


def test_populated_rollback_and_grants(reviews, isolated_database):
    _, _, _, engine, _, _ = reviews
    a, _, body, _ = reviewable(reviews)
    assert submit(reviews, a, body).status_code == 201
    with pytest.raises(DBAPIError, match="Human review data exists"):
        command.downgrade(isolated_database[1], "0008_synthetic_extraction")
    with engine.connect() as c:
        assert c.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
        assert not any(
            c.execute(
                text(
                    "SELECT rolsuper,rolcreatedb,rolcreaterole,rolbypassrls FROM pg_roles WHERE rolname='medlm_runtime'"
                )
            ).one()
        )
        assert c.scalar(
            text(
                "SELECT bool_and(relrowsecurity AND relforcerowsecurity) FROM pg_class WHERE oid IN ('medlm.analysis_reviews'::regclass,'medlm.analysis_prescription_lines'::regclass)"
            )
        )
        assert not c.scalar(
            text(
                "SELECT count(*) FROM pg_proc WHERE pronamespace='medlm'::regnamespace AND prosecdef"
            )
        )
        assert not c.scalar(
            text("SELECT has_table_privilege('medlm_runtime','medlm.analysis_reviews','UPDATE')")
        )

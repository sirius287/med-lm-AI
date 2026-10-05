import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text
from test_manual_medication_api import (
    BODY,
    activate,
    create,
    post,
)
from test_manual_medication_api import (
    auth_env as _auth,
)
from test_manual_medication_api import (
    isolated_database as _database,
)
from test_manual_medication_api import (
    manual as _manual,
)

auth_env, isolated_database, manual = _auth, _database, _manual


def test_conflicting_actions_are_serialized_and_edits_preserve_history(manual):
    client, engine, _ = manual
    record = activate(client, create(client))
    with engine.connect() as conn:
        first = conn.execute(
            text("SELECT id,planned_at FROM medlm.dose_occurrences ORDER BY planned_at LIMIT 1")
        ).first()
    time.sleep(max(0, (first.planned_at - datetime.now(UTC)).total_seconds()) + 0.05)

    def action(kind):
        other = TestClient(client.app)
        try:
            other.headers["Authorization"] = "Bearer synthetic-access"
            return post(
                other,
                f"/occurrences/{first.id}/events",
                dict(
                    event_id=str(uuid4()),
                    type=kind,
                    expected_version=1,
                    client_at=datetime.now(UTC).isoformat(),
                ),
            ).status_code
        finally:
            other.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(action, ["taken", "skipped"]))
    assert sorted(results) == [201, 409]
    response = client.patch(
        f"/api/v1/medications/{record['id']}",
        json=BODY | {"dose_text": "New literal instructions"},
        headers={"If-Match": f'"{record["version"]}"'},
    )
    assert response.status_code == 200, response.text
    assert response.json()["schedule"] is None
    with engine.connect() as conn:
        assert (
            conn.scalar(
                text("SELECT dose_snapshot->>'dose_text' FROM medlm.dose_occurrences WHERE id=:id"),
                {"id": first.id},
            )
            == BODY["dose_text"]
        )
        assert (
            conn.scalar(
                text("SELECT count(*) FROM medlm.dose_occurrences WHERE status='cancelled'")
            )
            > 0
        )
        assert conn.scalar(text("SELECT count(*) FROM medlm.dose_events")) == 1


def test_materialization_duplicates_pagination_and_preview_tampering(manual):
    client, engine, _ = manual
    m = create(client)
    now = datetime.now(UTC)
    s = dict(
        kind="daily_times",
        local_times=["08:00"],
        time_zone="Asia/Kolkata",
        start_date=now.date().isoformat(),
        open_ended=True,
    )
    p = post(client, f"/medications/{m['id']}/schedules/preview", s).json()
    body = dict(
        schedule=s | {"local_times": ["09:00"]},
        proposal_hash=p["proposal_hash"],
        expires_at=p["expires_at"],
        medication_version=p["medication_version"],
    )
    assert post(client, f"/medications/{m['id']}/schedules", body).status_code == 409
    body["schedule"] = s
    assert post(client, f"/medications/{m['id']}/schedules", body).status_code == 201
    dates = dict(
        from_date=now.date().isoformat(), to_date=(now + timedelta(days=5)).date().isoformat()
    )
    assert post(client, "/occurrences/materialize", dates).json()["generated"] == 0
    q = f"?from_date={dates['from_date']}&to_date={dates['to_date']}&limit=1"
    page = client.get("/api/v1/occurrences" + q)
    assert page.status_code == 200, page.text
    first = page.json()
    assert first["next_cursor"]
    second = client.get("/api/v1/occurrences" + q + "&cursor=" + first["next_cursor"]).json()
    assert second["items"][0]["id"] != first["items"][0]["id"]
    assert client.get("/api/v1/occurrences" + q + "&time_zone=invalid").status_code == 422

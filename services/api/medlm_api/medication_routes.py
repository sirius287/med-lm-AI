from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from medlm_domain.manual_medications import (
    ActivationInput,
    DoseEventInput,
    MaterializeInput,
    MedicationInput,
    ScheduleInput,
    iana_zone,
)
from medlm_domain.scheduling import local_instant

from medlm_api.auth import SessionRepository
from medlm_api.auth_dependencies import current_identity
from medlm_api.domain_idempotency import idempotent
from medlm_api.errors import AppError
from medlm_api.medication_contracts import (
    EventView,
    HistoryPage,
    MaterializeView,
    MedicationPage,
    MedicationView,
    OccurrencePage,
    PreviewView,
)
from medlm_api.medication_repository import medication, sql
from medlm_api.medication_service import MedicationService, cursor_id

router = APIRouter()


def context(request: Request, identity=Depends(current_identity)):
    principal = identity.principal
    with request.app.state.database.transaction(principal.user_id) as conn:
        # Same session lock as revocation; requests that wait behind logout fail closed.
        sql(
            conn,
            "SELECT pg_advisory_xact_lock(hashtextextended(:sid,3))",
            sid=str(principal.session_id),
        )
        sql(
            conn,
            "SELECT pg_advisory_xact_lock(hashtextextended(:uid,5))",
            uid=str(principal.user_id),
        )
        SessionRepository.check_access_in(conn, principal)
        yield MedicationService(
            conn, principal.user_id, request.app.state.settings.medication_encryption_key
        )


def post(service, operation, key, body, action):
    return idempotent(service.conn, service.user, operation, key, body, service.key, action)


def tag(response, result):
    response.headers["ETag"] = f'"{result["version"]}"'
    return result


@router.post("/medications", response_model=MedicationView, status_code=201)
def create(
    body: MedicationInput,
    response: Response,
    service=Depends(context),
    idempotency_key: str | None = Header(None),
):
    return tag(
        response,
        post(
            service,
            "create",
            idempotency_key,
            body.model_dump(mode="json"),
            lambda: service.create(body),
        ),
    )


@router.get("/medications", response_model=MedicationPage)
def listing(
    service=Depends(context),
    cursor: str | None = None,
    limit: int = Query(25, ge=1, le=100),
    include_deleted: bool = False,
):
    rows = (
        sql(
            service.conn,
            """SELECT * FROM medlm.medications WHERE origin='manual'
        AND (:deleted OR deleted_at IS NULL) AND id>:cursor ORDER BY id LIMIT :limit""",
            deleted=include_deleted,
            cursor=cursor_id(cursor),
            limit=limit + 1,
        )
        .mappings()
        .all()
    )
    return {
        "items": [service.view(dict(r)) for r in rows[:limit]],
        "next_cursor": str(rows[limit - 1].id) if len(rows) > limit else None,
    }


@router.get("/medications/{id}", response_model=MedicationView)
def detail(id: UUID, response: Response, service=Depends(context)):
    return tag(response, service.view(medication(service.conn, id, deleted=True)))


@router.patch("/medications/{id}", response_model=MedicationView)
def edit(
    id: UUID,
    body: MedicationInput,
    response: Response,
    service=Depends(context),
    if_match: str | None = Header(None),
):
    return tag(response, service.edit(id, body, if_match))


@router.delete("/medications/{id}", status_code=204)
def delete(
    id: UUID,
    service=Depends(context),
    if_match: str | None = Header(None),
    erase_history: bool = False,
):
    service.delete(id, if_match, erase_history)


@router.post("/medications/{id}/schedules/preview", response_model=PreviewView)
def preview(
    id: UUID,
    body: ScheduleInput,
    service=Depends(context),
    idempotency_key: str | None = Header(None),
):
    # Authorize before replay: removal immediately invalidates preview capabilities.
    medication(service.conn, id)
    return post(
        service,
        f"preview:{id}",
        idempotency_key,
        body.model_dump(mode="json"),
        lambda: service.preview(id, body),
    )


@router.post("/medications/{id}/schedules", response_model=MedicationView, status_code=201)
def activate(
    id: UUID,
    body: ActivationInput,
    response: Response,
    service=Depends(context),
    idempotency_key: str | None = Header(None),
):
    medication(service.conn, id)
    return tag(
        response,
        post(
            service,
            f"activate:{id}",
            idempotency_key,
            body.model_dump(mode="json"),
            lambda: service.activate(id, body),
        ),
    )


@router.post("/occurrences/materialize", response_model=MaterializeView)
def materialize(
    body: MaterializeInput, service=Depends(context), idempotency_key: str | None = Header(None)
):
    return post(
        service,
        "materialize",
        idempotency_key,
        body.model_dump(mode="json"),
        lambda: service.materialize(body.from_date, body.to_date),
    )


def bounds(start, end, zone):
    if not 2020 <= start.year <= 2100 or not 2020 <= end.year <= 2100:
        raise AppError(422, "invalid_range", "The requested date range is unsupported.")
    if not 0 <= (end - start).days <= 89:
        raise AppError(422, "invalid_range", "Choose at most 90 days.")
    try:
        tz = iana_zone(zone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise AppError(422, "invalid_timezone", "Choose a supported timezone.") from exc
    return (
        local_instant(datetime.combine(start, datetime.min.time()), tz),
        local_instant(datetime.combine(end + timedelta(days=1), datetime.min.time()), tz),
    )


@router.get("/occurrences", response_model=OccurrencePage)
def due(
    from_date: date,
    to_date: date,
    time_zone: str = "Asia/Kolkata",
    medication_id: UUID | None = None,
    cursor: str | None = None,
    limit: int = Query(25, ge=1, le=100),
    service=Depends(context),
):
    start, end = bounds(from_date, to_date, time_zone)
    rows = sql(
        service.conn,
        """SELECT o.id FROM medlm.dose_occurrences o
      JOIN medlm.medication_schedules s ON s.id=o.schedule_id
      JOIN medlm.medications m ON m.id=s.medication_id
      WHERE m.origin='manual' AND o.planned_at>=:start AND o.planned_at<:end
      AND (CAST(:m AS uuid) IS NULL OR s.medication_id=CAST(:m AS uuid))
      AND (:cursor=CAST('00000000-0000-0000-0000-000000000000' AS uuid) OR
        (o.planned_at,o.id)>(SELECT planned_at,id FROM medlm.dose_occurrences WHERE id=:cursor))
      ORDER BY o.planned_at,o.id LIMIT :limit""",
        start=start,
        end=end,
        m=str(medication_id) if medication_id else None,
        cursor=cursor_id(cursor),
        limit=limit + 1,
    ).all()
    return {
        "items": [service.occurrence(r.id) for r in rows[:limit]],
        "next_cursor": str(rows[limit - 1].id) if len(rows) > limit else None,
    }


@router.post("/occurrences/{id}/events", response_model=EventView, status_code=201)
def event(
    id: UUID,
    body: DoseEventInput,
    service=Depends(context),
    idempotency_key: str | None = Header(None),
):
    service.occurrence(id)
    return post(
        service,
        f"event:{id}",
        idempotency_key,
        body.model_dump(mode="json"),
        lambda: service.event(id, body),
    )


@router.get("/history", response_model=HistoryPage)
def history(
    from_date: date,
    to_date: date,
    time_zone: str = "Asia/Kolkata",
    medication_id: UUID | None = None,
    cursor: str | None = None,
    limit: int = Query(25, ge=1, le=100),
    service=Depends(context),
):
    start, end = bounds(from_date, to_date, time_zone)
    rows = (
        sql(
            service.conn,
            """SELECT e.*,o.dose_snapshot,o.original_local_time
      FROM medlm.dose_events e JOIN medlm.dose_occurrences o ON o.id=e.occurrence_id
      JOIN medlm.medication_schedules s ON s.id=o.schedule_id
      JOIN medlm.medications m ON m.id=s.medication_id
      WHERE m.origin='manual' AND e.recorded_at>=:start AND e.recorded_at<:end
      AND (CAST(:m AS uuid) IS NULL OR s.medication_id=CAST(:m AS uuid))
      AND (:cursor=CAST('00000000-0000-0000-0000-000000000000' AS uuid) OR
        (e.recorded_at,e.id)<(SELECT recorded_at,id FROM medlm.dose_events WHERE id=:cursor))
      ORDER BY e.recorded_at DESC,e.id DESC LIMIT :limit""",
            start=start,
            end=end,
            m=str(medication_id) if medication_id else None,
            cursor=cursor_id(cursor),
            limit=limit + 1,
        )
        .mappings()
        .all()
    )
    return {
        "items": [dict(r) for r in rows[:limit]],
        "next_cursor": str(rows[limit - 1].id) if len(rows) > limit else None,
    }

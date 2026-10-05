import hashlib
import hmac
import json
from datetime import timedelta
from uuid import UUID, uuid4

from medlm_domain.manual_medications import ScheduleInput, iana_zone
from medlm_domain.scheduling import occurrences

from medlm_api.domain_idempotency import canonical, utcnow
from medlm_api.errors import AppError
from medlm_api.medication_repository import check_version, medication, retire, sql


class MedicationService:
    def __init__(self, conn, user, key):
        self.conn, self.user, self.key = conn, user, key

    def view(self, row):
        schedule = sql(
            self.conn,
            """SELECT schedule FROM medlm.medication_schedules
            WHERE medication_id=:id AND retired_at IS NULL""",
            id=row["id"],
        ).scalar()
        return {
            **row,
            "route_text": row["instruction_snapshot"].get("route_text"),
            "instructions": row["instruction_snapshot"].get("instructions"),
            "schedule": schedule,
            "verification_status": "unverified",
        }

    def revise(self, id, body, revision):
        instruction = uuid4()
        sql(
            self.conn,
            """INSERT INTO medlm.medication_instruction_revisions
            (id,user_id,medication_id,revision,fields,origin)
            VALUES (:id,:u,:m,:v,CAST(:fields AS jsonb),'manual')""",
            id=instruction,
            u=self.user,
            m=id,
            v=revision,
            fields=body.model_dump_json(),
        )
        sql(
            self.conn,
            "UPDATE medlm.medications SET current_instruction_id=:r WHERE id=:id",
            r=instruction,
            id=id,
        )

    def create(self, body):
        if (
            sql(
                self.conn, "SELECT count(*) FROM medlm.medications WHERE deleted_at IS NULL"
            ).scalar()
            >= 100
        ):
            raise AppError(409, "medication_limit", "The active medication limit is reached.")
        id = uuid4()
        sql(
            self.conn,
            """INSERT INTO medlm.medications
            (id,user_id,display_name,strength_text,dose_text,origin,instruction_snapshot,reviewed_at,updated_at)
            VALUES (:id,:u,:name,:strength,:dose,'manual',CAST(:fields AS jsonb),now(),now())""",
            id=id,
            u=self.user,
            name=body.display_name,
            strength=body.strength_text,
            dose=body.dose_text,
            fields=body.model_dump_json(),
        )
        self.revise(id, body, 1)
        return self.view(medication(self.conn, id)), id

    def edit(self, id, body, match):
        row = medication(self.conn, id)
        check_version(row, match)
        now = utcnow()
        retire(self.conn, id, now)
        sql(
            self.conn,
            """UPDATE medlm.medications SET display_name=:name,strength_text=:strength,
            dose_text=:dose,instruction_snapshot=CAST(:fields AS jsonb),reviewed_at=:now,
            updated_at=:now,version=version+1 WHERE id=:id""",
            id=id,
            name=body.display_name,
            strength=body.strength_text,
            dose=body.dose_text,
            fields=body.model_dump_json(),
            now=now,
        )
        self.revise(id, body, row["version"] + 1)
        return self.view(medication(self.conn, id))

    def delete(self, id, match, erase):
        try:
            row = medication(self.conn, id, deleted=True)
        except AppError as exc:
            # A lost erasure response must be safely retryable without retaining medical text.
            if (
                exc.status == 404
                and sql(
                    self.conn,
                    """SELECT EXISTS(
                SELECT 1 FROM medlm.idempotency_records WHERE resource_id=:id
                AND invalidated AND expires_at>now())""",
                    id=id,
                ).scalar()
            ):
                return
            raise
        if not row["deleted_at"] or erase:
            check_version(row, match)
        # Erasure includes cached mutation responses, which can contain medical text.
        sql(
            self.conn,
            "UPDATE medlm.idempotency_records SET encrypted_response='',invalidated=true WHERE resource_id=:id",
            id=id,
        )
        now = utcnow()
        if erase:
            sql(self.conn, "DELETE FROM medlm.medications WHERE id=:id", id=id)
        elif not row["deleted_at"]:
            retire(self.conn, id, now)
            sql(
                self.conn,
                """UPDATE medlm.medications SET deleted_at=:now,updated_at=:now,
                version=version+1 WHERE id=:id""",
                id=id,
                now=now,
            )

    def signature(self, row, schedule, expires):
        if not self.key:
            raise AppError(503, "not_configured", "Manual management is not configured.")
        payload = canonical(
            {
                "user": self.user,
                "medication": row["id"],
                "version": row["version"],
                "schedule": schedule.model_dump(mode="json"),
                "expires_at": expires,
            }
        )
        return hmac.new(
            self.key.get_secret_value().encode(), payload.encode(), hashlib.sha256
        ).hexdigest()

    def preview(self, id, schedule):
        row = medication(self.conn, id)
        now = utcnow()
        expires = now + timedelta(minutes=10)
        start = max(schedule.start_date, now.astimezone(iana_zone(schedule.time_zone)).date())
        self.validate_materialization_range(start, start + timedelta(days=89))
        upcoming = occurrences(schedule, start, start + timedelta(days=89), now)
        if not upcoming:
            raise AppError(
                422, "empty_schedule", "No future doses occur within the next 90 schedule days."
            )
        return {
            "proposal_hash": self.signature(row, schedule, expires),
            "expires_at": expires,
            "medication_version": row["version"],
            "occurrences": upcoming[:10],
            "warnings": [
                "manual_unverified",
                "online_only_no_notifications",
                "dst_next_valid_first_overlap",
            ],
        }, id

    def activate(self, id, body):
        row = medication(self.conn, id)
        now = utcnow()
        if body.expires_at.tzinfo is None or not now < body.expires_at <= now + timedelta(
            minutes=10
        ):
            raise AppError(409, "preview_expired", "Review a fresh schedule preview.")
        check_version(row, f'"{body.medication_version}"')
        if not hmac.compare_digest(
            body.proposal_hash, self.signature(row, body.schedule, body.expires_at)
        ):
            raise AppError(409, "preview_mismatch", "Review the updated schedule.")
        if not row["current_instruction_id"]:
            raise AppError(
                409, "instruction_review_required", "Review and save the manual instructions first."
            )
        schedule = body.schedule
        start = max(schedule.start_date, now.astimezone(iana_zone(schedule.time_zone)).date())
        self.validate_materialization_range(start, start + timedelta(days=89))
        if not occurrences(schedule, start, start + timedelta(days=89), now):
            raise AppError(409, "preview_expired", "Review a fresh schedule preview.")
        retire(self.conn, id, now)
        revision = sql(
            self.conn,
            "SELECT coalesce(max(revision),0)+1 FROM medlm.medication_schedules WHERE medication_id=:id",
            id=id,
        ).scalar()
        sid = uuid4()
        sql(
            self.conn,
            """INSERT INTO medlm.medication_schedules
            (id,user_id,medication_id,revision,kind,schedule,time_zone,start_date,end_date,effective_at,instruction_revision_id)
            VALUES (:id,:u,:m,:v,:kind,CAST(:s AS jsonb),:zone,:start,:end,:effective,:instruction)""",
            id=sid,
            u=self.user,
            m=id,
            v=revision,
            kind=schedule.kind,
            s=schedule.model_dump_json(),
            zone=schedule.time_zone,
            start=schedule.start_date,
            end=schedule.end_date,
            effective=now,
            instruction=row["current_instruction_id"],
        )
        sql(
            self.conn,
            "UPDATE medlm.medications SET version=version+1,updated_at=:now WHERE id=:id",
            id=id,
            now=now,
        )
        self.materialize(start, start + timedelta(days=89), id)
        return self.view(medication(self.conn, id)), id

    @staticmethod
    def validate_materialization_range(start, end):
        if (end - start).days not in range(90):
            raise AppError(422, "invalid_range", "Choose at most 90 days.")
        # A request is bounded in date range, account size and schedule density.
        if end > utcnow().date() + timedelta(days=730) or start < utcnow().date() - timedelta(
            days=3650
        ):
            raise AppError(422, "invalid_range", "The requested date range is unsupported.")

    def materialize(self, start, end, medication_id=None):
        self.validate_materialization_range(start, end)
        rows = (
            sql(
                self.conn,
                """SELECT s.*, r.fields FROM medlm.medication_schedules s
            JOIN medlm.medications m ON m.id=s.medication_id AND m.user_id=s.user_id
            JOIN medlm.medication_instruction_revisions r ON r.id=s.instruction_revision_id AND r.user_id=s.user_id
            WHERE m.deleted_at IS NULL AND m.origin='manual' AND s.effective_at IS NOT NULL
              AND (CAST(:id AS uuid) IS NULL OR m.id=CAST(:id AS uuid))""",
                id=str(medication_id) if medication_id else None,
            )
            .mappings()
            .all()
        )
        count = 0
        for row in rows:
            for item in occurrences(
                ScheduleInput.model_validate(row.schedule), start, end, row.effective_at
            ):
                if row.retired_at and item["planned_at"] >= row.retired_at:
                    continue
                result = sql(
                    self.conn,
                    """INSERT INTO medlm.dose_occurrences
                    (id,user_id,schedule_id,occurrence_key,planned_at,dose_snapshot,original_local_time)
                    VALUES (:id,:u,:s,:key,:at,CAST(:snapshot AS jsonb),:local)
                    ON CONFLICT(schedule_id,occurrence_key) DO NOTHING""",
                    id=uuid4(),
                    u=self.user,
                    s=row.id,
                    key=item["planned_at"].isoformat(),
                    at=item["planned_at"],
                    snapshot=json.dumps(row.fields),
                    local=item["original_local_time"],
                )
                count += result.rowcount
        return {"generated": count}, None

    def occurrence(self, id):
        row = (
            sql(
                self.conn,
                """SELECT o.*,s.medication_id,m.deleted_at,
            (SELECT e.id FROM medlm.dose_events e WHERE e.occurrence_id=o.id
             ORDER BY e.occurrence_version DESC NULLS LAST,e.recorded_at DESC,e.id DESC LIMIT 1) latest_event_id
            FROM medlm.dose_occurrences o JOIN medlm.medication_schedules s ON s.id=o.schedule_id
            JOIN medlm.medications m ON m.id=s.medication_id
            WHERE o.id=:id AND m.origin='manual' FOR UPDATE OF o""",
                id=id,
            )
            .mappings()
            .first()
        )
        if not row:
            raise AppError(404, "occurrence_unavailable", "Dose is unavailable.")
        return {
            **row,
            "actionable": row.deleted_at is None
            and row.status != "cancelled"
            and row.planned_at <= utcnow(),
        }

    def event(self, id, body):
        row = self.occurrence(id)
        prior = (
            sql(self.conn, "SELECT * FROM medlm.dose_events WHERE id=:id", id=body.event_id)
            .mappings()
            .first()
        )
        if prior:
            if prior.occurrence_id != id or prior.payload != body.model_dump(mode="json"):
                raise AppError(409, "event_conflict", "This event identifier was already used.")
            return {"event_id": body.event_id, "occurrence": row}, row["medication_id"]
        if not row["actionable"]:
            raise AppError(409, "dose_not_actionable", "This dose cannot be changed.")
        if row["version"] != body.expected_version:
            raise AppError(409, "dose_conflict", "This dose changed. Reload and review.")
        if body.client_at > utcnow() + timedelta(minutes=5):
            raise AppError(422, "invalid_event_time", "Check the device clock.")
        if body.type == "corrected":
            if body.supersedes_event_id != row["latest_event_id"]:
                raise AppError(409, "correction_conflict", "Correct the latest event only.")
            status = body.corrected_status
        else:
            if row["status"] != "pending":
                raise AppError(
                    409, "dose_conflict", "Use an explicit correction for a recorded dose."
                )
            status = body.type
        sql(
            self.conn,
            """INSERT INTO medlm.dose_events
            (id,user_id,occurrence_id,kind,client_at,payload,supersedes_event_id,occurrence_version,recorded_at)
            VALUES (:id,:u,:o,:kind,:at,CAST(:p AS jsonb),:sup,:version,clock_timestamp())""",
            id=body.event_id,
            u=self.user,
            o=id,
            kind=body.type,
            at=body.client_at,
            p=body.model_dump_json(),
            sup=body.supersedes_event_id,
            version=row["version"] + 1,
        )
        sql(
            self.conn,
            "UPDATE medlm.dose_occurrences SET status=:s,version=version+1 WHERE id=:id",
            s=status,
            id=id,
        )
        return {"event_id": body.event_id, "occurrence": self.occurrence(id)}, row["medication_id"]


def cursor_id(value):
    if value is None:
        return UUID(int=0)
    try:
        return UUID(value)
    except ValueError as exc:
        raise AppError(422, "invalid_cursor", "Reload the list.") from exc

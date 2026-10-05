"""SQL uses only verified transaction-local ownership context."""

from sqlalchemy import text

from medlm_api.errors import AppError


def sql(conn, statement, **params):
    return conn.execute(text(statement), params)


def medication(conn, medication_id, *, deleted=False):
    row = (
        sql(conn, "SELECT * FROM medlm.medications WHERE id=:id FOR UPDATE", id=medication_id)
        .mappings()
        .first()
    )
    if not row or (row.deleted_at and not deleted):
        raise AppError(404, "medication_unavailable", "Medication is unavailable.")
    if row.origin != "manual":
        raise AppError(409, "manual_only", "This operation supports manual records only.")
    return dict(row)


def check_version(row, value):
    if value is None:
        raise AppError(428, "version_required", "Reload before making this change.")
    if value != f'"{row["version"]}"':
        raise AppError(412, "stale_version", "This record changed. Reload and review.")


def retire(conn, medication_id, now):
    sql(
        conn,
        """UPDATE medlm.medication_schedules SET retired_at=:now
        WHERE medication_id=:id AND retired_at IS NULL""",
        id=medication_id,
        now=now,
    )
    sql(
        conn,
        """UPDATE medlm.dose_occurrences SET status='cancelled',version=version+1
        WHERE schedule_id IN (SELECT id FROM medlm.medication_schedules WHERE medication_id=:id)
        AND status='pending' AND planned_at>=:now""",
        id=medication_id,
        now=now,
    )

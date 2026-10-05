import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from fastapi.encoders import jsonable_encoder

from medlm_api.errors import AppError
from medlm_api.medication_repository import sql


def canonical(value):
    return json.dumps(jsonable_encoder(value), sort_keys=True, separators=(",", ":"))


def idempotent(conn, user, operation, key, body, encryption_key, action):
    try:
        key = UUID(key or "")
    except ValueError as exc:
        raise AppError(428, "idempotency_required", "A request key is required.") from exc
    if not encryption_key:
        raise AppError(503, "not_configured", "Manual management is not configured.")
    cipher = Fernet(encryption_key.get_secret_value().encode())
    digest = hashlib.sha256(canonical(body).encode()).hexdigest()
    sql(conn, "DELETE FROM medlm.idempotency_records WHERE expires_at<=now()")
    prior = (
        sql(
            conn,
            """SELECT * FROM medlm.idempotency_records
        WHERE user_id=:u AND operation=:op AND key=:k""",
            u=user,
            op=operation,
            k=key,
        )
        .mappings()
        .first()
    )
    if prior:
        if prior.invalidated:
            raise AppError(410, "request_removed", "This request belongs to a removed record.")
        if prior.request_hash != digest:
            raise AppError(409, "idempotency_conflict", "Use a new request key for changed input.")
        try:
            return json.loads(cipher.decrypt(prior.encrypted_response.encode()))
        except InvalidToken as exc:
            raise AppError(503, "idempotency_unavailable", "Retry later.", True) from exc
    response, resource = action()
    encoded = jsonable_encoder(response)
    sql(
        conn,
        """INSERT INTO medlm.idempotency_records
        (user_id,operation,key,request_hash,encrypted_response,resource_id)
        VALUES (:u,:op,:k,:h,:response,:resource)""",
        u=user,
        op=operation,
        k=key,
        h=digest,
        response=cipher.encrypt(canonical(encoded).encode()).decode(),
        resource=resource,
    )
    return encoded


def utcnow():
    return datetime.now(UTC)

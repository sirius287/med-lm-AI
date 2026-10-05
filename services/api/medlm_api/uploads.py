"""Synthetic-only upload application service; never mounted by the normal app."""

import hashlib
import hmac
import json
import secrets
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from medlm_api.auth import SessionRepository, digest
from medlm_api.errors import AppError
from medlm_api.images import UploadRequest, validate_image
from medlm_api.upload_storage import ObjectStorage


def utcnow():
    return datetime.now(UTC)


def sql(conn, statement, **params):
    return conn.execute(text(statement), params)


def storage_lock(conn):
    # All local harness writers and independent reconcilers share this lock.
    # Intentionally serializes bounded local IO; not a production throughput design.
    sql(conn, "SELECT pg_advisory_xact_lock(73042,1)")


class SyntheticUploadRequest(UploadRequest):
    consent_version: Literal["synthetic-v1"]
    checksum_sha256: str = Field(pattern="^[0-9a-f]{64}$")


class CompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    checksum_sha256: str = Field(pattern="^[0-9a-f]{64}$")


class UploadState(BaseModel):
    upload_id: UUID
    status: Literal["initiated", "accepted", "rejected", "deleting", "deleted"]
    version: int
    purge_at: datetime


class UploadIntent(UploadState):
    upload_url: str
    ticket: str | None
    upload_expires_at: datetime


class DeletionReceipt(BaseModel):
    receipt_id: UUID
    verified_at: datetime
    expires_at: datetime


class ReceiptList(BaseModel):
    receipts: list[DeletionReceipt]


def state(row):
    return UploadState(
        upload_id=row.id, status=row.status, version=row.version, purge_at=row.expires_at
    )


def audit(conn, row, event):
    sql(
        conn,
        """INSERT INTO medlm.upload_audit_events
        (id,user_id,upload_id,event,expires_at)
        VALUES (:id,:uid,:upload,:event,now()+interval '90 days')""",
        id=uuid4(),
        uid=row.user_id,
        upload=row.id,
        event=event,
    )


def queue_delete(conn, row, reason):
    if row.status == "deleted":
        return
    if row.status != "deleting":
        sql(
            conn,
            """UPDATE medlm.uploads SET status='deleting',
            deletion_requested_at=clock_timestamp() WHERE id=:id""",
            id=row.id,
        )
        audit(conn, row, "deletion_requested")
    objects = sql(
        conn,
        """SELECT id FROM medlm.upload_objects
        WHERE upload_id=:id AND purged_at IS NULL""",
        id=row.id,
    ).all()
    for obj in objects:
        sql(
            conn,
            """INSERT INTO medlm.upload_deletion_jobs
            (id,user_id,upload_id,object_id,reason) VALUES (:id,:uid,:upload,:obj,:reason)
            ON CONFLICT(object_id) DO NOTHING""",
            id=uuid4(),
            uid=row.user_id,
            upload=row.id,
            obj=obj.id,
            reason=reason,
        )


class SyntheticUploads:
    def __init__(
        self,
        storage: ObjectStorage,
        allowed_checksums: frozenset[str],
        *,
        ttl_seconds=3600,
        clock=utcnow,
    ):
        if not allowed_checksums or not 1 <= ttl_seconds <= 86400:
            raise ValueError("Controlled synthetic fixtures and bounded retention required")
        self.storage, self.allowed = storage, allowed_checksums
        self.ttl, self.clock = ttl_seconds, clock

    @contextmanager
    def owned(self, db, principal):
        with db.transaction(principal.user_id) as conn:
            # Same fence as logout. Disabled-account update also waits for this lock.
            sql(
                conn,
                "SELECT pg_advisory_xact_lock(hashtextextended(:sid,3))",
                sid=str(principal.session_id),
            )
            sql(conn, "SELECT id FROM medlm.users WHERE id=:id FOR SHARE", id=principal.user_id)
            SessionRepository.check_access_in(conn, principal)
            if principal.expires_at <= self.clock():
                raise AppError(401, "invalid_session", "Sign in again.")
            yield conn

    def health(self, conn):
        rows = sql(
            conn,
            """SELECT DISTINCT ON(kind) kind,outcome,finished_at,overdue_objects
            FROM medlm.upload_safeguard_runs ORDER BY kind,started_at DESC""",
        ).all()
        if len(rows) != 3 or any(
            r.outcome != "ok"
            or r.overdue_objects
            or r.finished_at is None
            or r.finished_at < self.clock() - timedelta(minutes=5)
            for r in rows
        ):
            raise AppError(503, "deletion_unhealthy", "Uploads are temporarily unavailable.", True)

    def row(self, conn, upload_id, *, active=False):
        row = sql(conn, "SELECT * FROM medlm.uploads WHERE id=:id FOR UPDATE", id=upload_id).first()
        if row is None:
            raise AppError(404, "not_found", "Upload is unavailable.")
        if active and (
            row.expires_at <= self.clock() or row.status in ("rejected", "deleting", "deleted")
        ):
            raise AppError(410, "upload_expired", "Upload is no longer available.")
        return row

    @staticmethod
    def match(row, version):
        if version is None:
            raise AppError(428, "version_required", "Supply the current upload version.")
        if version != f'"{row.version}"':
            raise AppError(412, "stale_version", "Reload the upload status.")

    def create(self, db, principal, body, key):
        request_hash = digest(json.dumps(body.model_dump(), sort_keys=True))
        with self.owned(db, principal) as conn:
            # Serializes per-user quota and idempotency checks across API instances.
            sql(
                conn,
                "SELECT pg_advisory_xact_lock(hashtextextended(:uid,4))",
                uid=str(principal.user_id),
            )
            previous = sql(
                conn, "SELECT * FROM medlm.uploads WHERE request_key=:key", key=key
            ).first()
            if previous:
                if previous.request_hash != request_hash:
                    raise AppError(409, "idempotency_conflict", "Use a new request key.")
                return self.intent(previous, None)
            self.health(conn)
            if body.checksum_sha256 not in self.allowed:
                raise AppError(
                    403, "synthetic_only", "Only controlled synthetic fixtures are allowed."
                )
            counts = sql(
                conn,
                """SELECT count(*) AS count,coalesce(sum(declared_bytes),0) AS size
                FROM medlm.uploads WHERE status <> 'deleted'""",
            ).first()
            if counts.count >= 5 or counts.size + body.byte_size > 30 * 1024 * 1024:
                raise AppError(429, "upload_quota", "Delete existing synthetic uploads first.")
            ticket, now, upload_id = secrets.token_urlsafe(32), self.clock(), uuid4()
            row = sql(
                conn,
                """INSERT INTO medlm.uploads
                (id,user_id,notice_version,document_kind,mime,declared_bytes,ticket_hash,
                 ticket_expires_at,retain_for_review,expires_at,created_at,request_key,
                 request_hash,source_checksum_sha256)
                VALUES (:id,:uid,:notice,:kind,:mime,:size,:ticket,:ticket_end,:review,
                        :expiry,:now,:key,:hash,:checksum) RETURNING *""",
                id=upload_id,
                uid=principal.user_id,
                notice=body.consent_version,
                kind=body.document_kind,
                mime=body.content_type,
                size=body.byte_size,
                ticket=digest(ticket),
                ticket_end=now + timedelta(seconds=min(300, self.ttl)),
                review=body.retain_for_review,
                expiry=now + timedelta(seconds=self.ttl),
                now=now,
                key=key,
                hash=request_hash,
                checksum=body.checksum_sha256,
            ).first()
            audit(conn, row, "initiated")
            return self.intent(row, ticket)

    @staticmethod
    def intent(row, ticket):
        return UploadIntent(
            **state(row).model_dump(),
            upload_url=f"/uploads/{row.id}/content",
            ticket=ticket,
            upload_expires_at=row.ticket_expires_at,
        )

    def reserve(self, db, principal, upload_id, ticket, mime):
        with self.owned(db, principal) as conn:
            self.health(conn)
            row = self.row(conn, upload_id, active=True)
            if row.consumed_at or row.ticket_expires_at <= self.clock():
                raise AppError(410, "ticket_unavailable", "Create a new upload.")
            if not ticket or not hmac.compare_digest(digest(ticket), row.ticket_hash):
                raise AppError(403, "invalid_ticket", "Upload ticket is invalid.")
            if mime != row.mime:
                raise AppError(415, "unsupported_image_type", "Content type does not match.")
            sql(
                conn,
                "UPDATE medlm.uploads SET consumed_at=:now WHERE id=:id",
                now=self.clock(),
                id=row.id,
            )
            # Durable inventory precedes any filesystem write (even a process crash).
            obj = uuid4()
            sql(
                conn,
                """INSERT INTO medlm.upload_objects
                (id,user_id,upload_id,object_key,kind,expires_at)
                VALUES (:id,:uid,:upload,:key,:kind,:expiry)""",
                id=obj,
                uid=row.user_id,
                upload=row.id,
                key=uuid4(),
                kind="review" if row.retain_for_review else "sanitized",
                expiry=row.expires_at,
            )
            return row.declared_bytes

    def write(self, db, principal, upload_id, data, settings):
        checksum = hashlib.sha256(data).hexdigest()
        if checksum not in self.allowed:
            raise AppError(403, "synthetic_only", "Only controlled synthetic fixtures are allowed.")
        with self.owned(db, principal) as conn:
            storage_lock(conn)
            self.health(conn)
            row = self.row(conn, upload_id, active=True)
            if row.ticket_expires_at <= self.clock():
                raise AppError(410, "ticket_unavailable", "Upload transfer expired.")
            if len(data) != row.declared_bytes or checksum != row.source_checksum_sha256:
                raise AppError(422, "content_mismatch", "Upload does not match its declaration.")
            clean = validate_image(
                data, row.mime, settings.max_image_bytes, settings.max_image_pixels
            )
            obj = sql(
                conn, "SELECT * FROM medlm.upload_objects WHERE upload_id=:id", id=upload_id
            ).one()
            if obj.checksum_sha256 or obj.purged_at:
                raise AppError(409, "immutable_upload", "Upload cannot be replaced.")
            if principal.expires_at <= self.clock():
                raise AppError(401, "invalid_session", "Sign in again.")
            self.storage.put(row.user_id, obj.object_key, clean)
            # Any database failure leaves the previously committed inventory available to sweep.
            sql(
                conn,
                """UPDATE medlm.upload_objects SET checksum_sha256=:hash,byte_size=:size
                WHERE id=:id""",
                hash=hashlib.sha256(clean).hexdigest(),
                size=len(clean),
                id=obj.id,
            )

    def reject(self, db, principal, upload_id):
        # No new clinical work: cleanup remains possible after logout.
        with db.transaction(principal.user_id) as conn:
            row = self.row(conn, upload_id)
            queue_delete(conn, row, "rejected")

    def get(self, db, principal, upload_id):
        with self.owned(db, principal) as conn:
            return state(self.row(conn, upload_id))

    def complete(self, db, principal, upload_id, body, version):
        with self.owned(db, principal) as conn:
            storage_lock(conn)
            row = self.row(conn, upload_id, active=True)
            if body.checksum_sha256 != row.source_checksum_sha256:
                raise AppError(409, "content_mismatch", "Checksum does not match.")
            if row.accepted_at:
                return state(row)
            self.match(row, version)
            obj = sql(
                conn, "SELECT * FROM medlm.upload_objects WHERE upload_id=:id", id=upload_id
            ).first()
            if obj is None or obj.checksum_sha256 is None or obj.purged_at:
                raise AppError(409, "upload_incomplete", "Finish the content transfer first.")
            data = self.storage.read(row.user_id, obj.object_key)
            if hashlib.sha256(data).hexdigest() != obj.checksum_sha256:
                raise AppError(409, "content_mismatch", "Stored content is unavailable.")
            row = sql(
                conn,
                """UPDATE medlm.uploads SET status='accepted',accepted_at=:now
                WHERE id=:id RETURNING *""",
                now=self.clock(),
                id=upload_id,
            ).first()
            audit(conn, row, "accepted")
            if not row.retain_for_review:
                queue_delete(conn, row, "completed")
                row = self.row(conn, upload_id)
            return state(row)

    def delete(self, db, principal, upload_id, version):
        with self.owned(db, principal) as conn:
            row = self.row(conn, upload_id)
            if row.status not in ("deleting", "deleted"):
                self.match(row, version)
                queue_delete(conn, row, "cancelled")
            return state(self.row(conn, upload_id))

    def preview(self, db, principal, upload_id):
        with self.owned(db, principal) as conn:
            storage_lock(conn)
            row = self.row(conn, upload_id, active=True)
            if row.status != "accepted" or not row.retain_for_review:
                raise AppError(409, "preview_unavailable", "Review image is unavailable.")
            obj = sql(
                conn,
                """SELECT * FROM medlm.upload_objects WHERE upload_id=:id
                AND purged_at IS NULL AND expires_at>:now""",
                id=upload_id,
                now=self.clock(),
            ).first()
            if obj is None:
                raise AppError(410, "upload_expired", "Image is unavailable.")
            return self.storage.read(row.user_id, obj.object_key)

    def receipts(self, db, principal, upload_id):
        with self.owned(db, principal) as conn:
            self.row(conn, upload_id)
            rows = sql(
                conn,
                """SELECT r.id AS receipt_id,r.verified_at,r.expires_at
                FROM medlm.upload_deletion_receipts r JOIN medlm.upload_objects o
                ON o.object_key=r.object_key WHERE o.upload_id=:id AND r.expires_at>:now""",
                id=upload_id,
                now=self.clock(),
            ).mappings()
            return ReceiptList(receipts=[DeletionReceipt(**r) for r in rows])

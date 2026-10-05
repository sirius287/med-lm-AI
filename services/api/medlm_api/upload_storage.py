"""Encrypted local synthetic storage. Not a production or Supabase adapter."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken

from medlm_api.errors import AppError


class ObjectStorage(Protocol):
    def put(self, owner: UUID, key: UUID, data: bytes) -> None: ...
    def read(self, owner: UUID, key: UUID) -> bytes: ...
    def delete(self, key: UUID) -> None: ...
    def exists(self, key: UUID) -> bool: ...
    def keys(self) -> list[UUID]: ...
    def record_deletion(self, key: UUID, verified_at: datetime, expires_at: datetime) -> None: ...
    def deletion_ledger(self) -> list[dict]: ...
    def expire_receipts(self, now: datetime) -> None: ...


class LocalSyntheticStorage:
    """Opaque immutable keys, encrypted owner binding, no plaintext spool files.

    Directory must be private to the service OS account; encryption is not an ACL.
    All writers/maintenance use database locks. OS-admin tampering is out of scope.
    """

    def __init__(self, root: Path, key: bytes):
        if not root.is_absolute() or root.is_symlink():
            raise ValueError("Storage requires an absolute private directory")
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.ledger = self.root.with_name(self.root.name + ".deletion-ledger")
        if self.ledger.is_symlink():
            raise ValueError("Receipt ledger cannot be a link")
        self.ledger.mkdir(mode=0o700, exist_ok=True)
        self.cipher = Fernet(key)

    def _path(self, key: UUID) -> Path:
        if not isinstance(key, UUID):
            raise ValueError("Opaque UUID required")
        path = self.root / str(key)
        if path.is_symlink():
            raise OSError("Unexpected storage link")
        return path

    def put(self, owner: UUID, key: UUID, data: bytes) -> None:
        if not data or len(data) > 10485760:
            raise ValueError("Invalid object size")
        if (self.ledger / str(key)).exists():
            raise OSError("Deleted object cannot be recreated")
        payload = self.cipher.encrypt(owner.bytes + data)
        # Exclusive creation: an interrupted write remains inventoried for deletion.
        with self._path(key).open("xb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())

    def read(self, owner: UUID, key: UUID) -> bytes:
        if (self.ledger / str(key)).exists():
            raise AppError(410, "upload_expired", "Image is no longer available.")
        path = self._path(key)
        if path.stat().st_size > 15 * 1024 * 1024:
            raise OSError("Invalid encrypted size")
        try:
            payload = self.cipher.decrypt(path.read_bytes())
        except InvalidToken as exc:
            raise OSError("Unreadable object") from exc
        if payload[:16] != owner.bytes:
            raise AppError(404, "not_found", "Image is unavailable.")
        return payload[16:]

    def delete(self, key: UUID) -> None:
        self._path(key).unlink(missing_ok=True)

    def exists(self, key: UUID) -> bool:
        return self._path(key).exists()

    def keys(self) -> list[UUID]:
        result = []
        for path in self.root.iterdir():
            if not path.is_file() or path.is_symlink():
                raise OSError("Unexpected storage entry")
            try:
                result.append(UUID(path.name))
            except ValueError as exc:
                raise OSError("Unexpected storage entry") from exc
            if len(result) > 10000:
                raise OSError("Synthetic storage capacity exceeded")
        return result

    def record_deletion(self, key: UUID, verified_at: datetime, expires_at: datetime) -> None:
        if self.exists(key):
            raise OSError("Object still exists")
        path = self.ledger / str(key)
        if path.is_symlink():
            raise OSError("Unexpected receipt link")
        if path.exists():
            return
        payload = json.dumps(
            {
                "object_key": str(key),
                "verified_at": verified_at.isoformat(),
                "expires_at": expires_at.isoformat(),
            }
        ).encode()
        with path.open("xb") as output:
            output.write(self.cipher.encrypt(payload))
            output.flush()
            os.fsync(output.fileno())

    def deletion_ledger(self) -> list[dict]:
        result = []
        try:
            for path in self.ledger.iterdir():
                if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
                    raise OSError("Invalid deletion receipt")
                value = json.loads(self.cipher.decrypt(path.read_bytes()))
                if str(UUID(path.name)) != value["object_key"]:
                    raise ValueError()
                result.append(
                    {
                        "object_key": UUID(value["object_key"]),
                        "verified_at": datetime.fromisoformat(value["verified_at"]),
                        "expires_at": datetime.fromisoformat(value["expires_at"]),
                    }
                )
                if len(result) > 10000:
                    raise OSError("Receipt capacity exceeded")
        except (ValueError, KeyError, InvalidToken) as exc:
            raise OSError("Unreadable deletion ledger") from exc
        return result

    def expire_receipts(self, now: datetime) -> None:
        for receipt in self.deletion_ledger():
            if receipt["expires_at"] <= now:
                (self.ledger / str(receipt["object_key"])).unlink()

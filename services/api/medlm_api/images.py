import io
import threading
import time
import warnings
from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid4

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field

from medlm_api.errors import AppError

MIME_FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}


class UploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_type: Literal["image/jpeg", "image/png", "image/webp"]
    byte_size: int = Field(gt=0, le=10 * 1024 * 1024)
    document_kind: str = Field(pattern="^(strip|bottle|tube|box|prescription)$")
    retain_for_review: bool = False


def validate_image(data: bytes, mime: str, max_bytes: int, max_pixels: int) -> bytes:
    """Decode and re-encode to remove metadata. Never trusts file extensions."""
    if mime not in MIME_FORMATS:
        raise AppError(415, "unsupported_image_type", "Use JPEG, PNG or WebP.")
    if not data or len(data) > max_bytes:
        raise AppError(413, "image_size", "Image exceeds the permitted size.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as probe:
                if probe.format != MIME_FORMATS[mime] or probe.width * probe.height > max_pixels:
                    raise ValueError("type or dimensions")
                if getattr(probe, "n_frames", 1) != 1:
                    raise ValueError("animated image")
                probe.verify()
            with Image.open(io.BytesIO(data)) as decoded:
                decoded.load()
                clean = Image.new("RGB", decoded.size)
                clean.paste(decoded.convert("RGB"))
                output = io.BytesIO()
                clean.save(output, format="PNG")
                result = output.getvalue()
                if len(result) > max_bytes:
                    raise AppError(413, "image_size", "Decoded image exceeds the permitted size.")
                return result
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
    ) as exc:
        raise AppError(422, "invalid_image", "Image cannot be safely decoded.") from exc


@dataclass
class _Entry:
    owner: UUID
    data: bytes
    expires: float


class MemoryTemporaryStorage:
    """Bounded nonpersistent prototype. Not wired to public upload routes."""

    def __init__(
        self, ttl_seconds: int = 300, max_total_bytes: int = 30 * 1024 * 1024, clock=time.monotonic
    ):
        if not 0 < ttl_seconds <= 86400 or max_total_bytes <= 0:
            raise ValueError("Invalid temporary storage bounds")
        self.ttl = ttl_seconds
        self.limit = max_total_bytes
        self.clock = clock
        self._entries: dict[UUID, _Entry] = {}
        self._lock = threading.RLock()

    def purge_expired(self) -> int:
        with self._lock:
            keys = [key for key, value in self._entries.items() if value.expires <= self.clock()]
            for key in keys:
                del self._entries[key]
            return len(keys)

    def put(self, owner: UUID, data: bytes) -> UUID:
        with self._lock:
            self.purge_expired()
            if sum(len(v.data) for v in self._entries.values()) + len(data) > self.limit:
                raise AppError(503, "storage_capacity", "Temporary storage is full.", True)
            key = uuid4()
            self._entries[key] = _Entry(owner, data, self.clock() + self.ttl)
            return key

    def read(self, owner: UUID, key: UUID) -> bytes:
        with self._lock:
            self.purge_expired()
            entry = self._entries.get(key)
            if entry is None or entry.owner != owner:
                raise AppError(404, "not_found", "Image is unavailable.")
            return entry.data

    def delete(self, owner: UUID, key: UUID) -> None:
        with self._lock:
            self.read(owner, key)
            del self._entries[key]

"""10 attempts per 60-second window; PostgreSQL serializes configured deployments."""

import hashlib
import hmac
import secrets
import time
from collections import deque
from threading import Lock

from sqlalchemy import text

from medlm_api.errors import AppError, unavailable


class AuthRateLimiter:
    def __init__(self, settings, database):
        self.settings, self.db = settings, database
        # Existing session key is a development compatibility fallback only.
        key = settings.auth_rate_limit_key or settings.session_encryption_key
        self.key = key.get_secret_value().encode() if key else secrets.token_bytes(32)
        self.configured_key = key is not None
        self.attempts = {}
        self.lock = Lock()

    def check(self, address: str):
        key = hmac.new(self.key, b"auth-ip:" + address.encode(), hashlib.sha256).hexdigest()
        if self.db.engine is not None:
            if not self.configured_key:
                raise unavailable("Shared authentication throttling")
            with self.db.transaction() as conn:
                attempts = conn.scalar(
                    text("""INSERT INTO medlm_auth.auth_throttles
                    (key_hash,window_end,attempts) VALUES (:key,clock_timestamp()+interval '60 seconds',1)
                    ON CONFLICT(key_hash) DO UPDATE SET
                    attempts=CASE WHEN medlm_auth.auth_throttles.window_end <= clock_timestamp()
                      THEN 1 ELSE LEAST(medlm_auth.auth_throttles.attempts+1,11) END,
                    window_end=CASE WHEN medlm_auth.auth_throttles.window_end <= clock_timestamp()
                      THEN clock_timestamp()+interval '60 seconds' ELSE medlm_auth.auth_throttles.window_end END
                    RETURNING attempts"""),
                    {"key": key},
                )
        else:
            if self.settings.environment == "production":
                raise unavailable("Database")
            # Unconfigured local shell only; a DB error never falls back here.
            with self.lock:
                now = time.monotonic()
                for stale in [k for k, q in self.attempts.items() if not q or q[-1] < now - 60]:
                    del self.attempts[stale]
                q = self.attempts.setdefault(key, deque(maxlen=11))
                while q and q[0] <= now - 60:
                    q.popleft()
                q.append(now)
                attempts = len(q)
        if attempts > 10:
            raise AppError(429, "rate_limited", "Try again later.", True)

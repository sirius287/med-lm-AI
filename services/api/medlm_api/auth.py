import hashlib
import json
import math
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import jwt
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from sqlalchemy import text

from medlm_api.config import Settings
from medlm_api.database import Database
from medlm_api.errors import AppError, unavailable


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def token_payload(value, *, stored=False):
    try:
        if not isinstance(value, dict):
            raise ValueError()
        result = {k: value[k] for k in ("access_token", "refresh_token")}
        if any(not isinstance(v, str) or not v or len(v) > 32768 for v in result.values()):
            raise ValueError()
        if stored:
            expiry = value["expires_at"]
            if (
                isinstance(expiry, bool)
                or not isinstance(expiry, (int, float))
                or not math.isfinite(expiry)
            ):
                raise ValueError()
            result["expires_at"] = expiry
        return result
    except (KeyError, ValueError, TypeError) as exc:
        raise AppError(
            401 if stored else 503,
            "invalid_session" if stored else "auth_unavailable",
            "Sign in again." if stored else "Authentication is unavailable.",
            not stored,
        ) from exc


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    session_id: UUID
    expires_at: datetime


class SupabaseGateway:
    """Real provider adapter. Tests replace only the network boundary."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client or httpx.Client(timeout=10, follow_redirects=False)
        self.jwks = (
            jwt.PyJWKClient(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json",
                cache_jwk_set=True,
                lifespan=300,
                timeout=10,
            )
            if settings.supabase_url
            else None
        )

    def _request(self, method: str, path: str, body=None, token: str | None = None):
        s = self.settings
        if not s.supabase_url or not s.supabase_publishable_key:
            raise unavailable("Supabase Auth")
        headers = {"apikey": s.supabase_publishable_key.get_secret_value()}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = self.client.request(
                method, f"{s.supabase_url.rstrip('/')}/auth/v1/{path}", json=body, headers=headers
            )
        except httpx.HTTPError as exc:
            raise AppError(503, "auth_unavailable", "Authentication is unavailable.", True) from exc
        if response.status_code >= 500 or response.status_code == 429:
            raise AppError(503, "auth_unavailable", "Authentication is unavailable.", True)
        if response.status_code >= 400:
            raise AppError(401, "authentication_failed", "Authentication could not be completed.")
        if response.status_code >= 300:
            raise AppError(503, "auth_unavailable", "Authentication is unavailable.", True)
        try:
            value = response.json() if response.content else {}
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except ValueError as exc:
            raise AppError(503, "auth_unavailable", "Authentication is unavailable.", True) from exc

    def register(self, email: str, password: str):
        self._request("POST", "signup", {"email": email, "password": password})

    def login(self, email: str, password: str) -> dict:
        return self._request(
            "POST", "token?grant_type=password", {"email": email, "password": password}
        )

    def refresh(self, refresh_token: str) -> dict:
        return self._request(
            "POST", "token?grant_type=refresh_token", {"refresh_token": refresh_token}
        )

    def logout(self, token: str):
        self._request("POST", "logout?scope=local", token=token)

    def verify_local(self, token: str, *, allow_expired=False) -> Principal:
        if self.jwks is None:
            raise unavailable("Supabase Auth")
        try:
            key = self.jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["ES256", "RS256"],
                audience="authenticated",
                issuer=f"{self.settings.supabase_url.rstrip('/')}/auth/v1",
                options={
                    "require": ["exp", "sub", "session_id", "iss", "aud"],
                    "verify_exp": not allow_expired,
                },
            )
            principal = Principal(
                UUID(claims["sub"]),
                UUID(claims["session_id"]),
                datetime.fromtimestamp(claims["exp"], UTC),
            )
        except jwt.PyJWKClientConnectionError as exc:
            raise AppError(503, "auth_unavailable", "Authentication is unavailable.", True) from exc
        except (jwt.PyJWTError, ValueError, KeyError, TypeError, OverflowError, OSError) as exc:
            raise AppError(401, "invalid_session", "Sign in again.") from exc
        return principal

    def verify(self, token: str) -> Principal:
        principal = self.verify_local(token)
        # Identity check, not a claim that /user proves auth.sessions still exists.
        user = self._request("GET", "user", token=token)
        if user.get("id") != str(principal.user_id):
            raise AppError(401, "invalid_session", "Sign in again.")
        if principal.expires_at <= datetime.now(UTC):
            raise AppError(401, "invalid_session", "Sign in again.")
        return principal

    def close(self):
        self.client.close()


class SessionRepository:
    def __init__(self, db: Database):
        self.db = db

    def ensure_user(self, principal: Principal):
        with self.db.transaction(principal.user_id) as conn:
            conn.execute(
                text("INSERT INTO medlm.users(id) VALUES (:id) ON CONFLICT DO NOTHING"),
                {"id": principal.user_id},
            )
            conn.execute(
                text("INSERT INTO medlm.profiles(user_id) VALUES (:id) ON CONFLICT DO NOTHING"),
                {"id": principal.user_id},
            )
        self.check_access(principal)

    def check_access(self, principal: Principal):
        with self.db.transaction(principal.user_id) as conn:
            self.check_access_in(conn, principal)

    @staticmethod
    def check_access_in(conn, principal: Principal):
        row = conn.execute(
            text("SELECT disabled_at FROM medlm.users WHERE id=:id"), {"id": principal.user_id}
        ).first()
        revoked = conn.scalar(
            text("SELECT 1 FROM medlm_auth.revoked_sessions WHERE session_id=:id"),
            {"id": principal.session_id},
        )
        if row is None or row.disabled_at or revoked:
            raise AppError(401, "invalid_session", "Sign in again.")

    @staticmethod
    def revoke_in(conn, principal: Principal):
        # Upload publication takes the same lock before its final access check.
        conn.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:sid,3))"),
            {"sid": str(principal.session_id)},
        )
        conn.execute(
            text("""INSERT INTO medlm_auth.revoked_sessions
              (session_id,user_id,expires_at) VALUES (:sid,:uid,:exp)
              ON CONFLICT(session_id) DO NOTHING"""),
            {
                "sid": principal.session_id,
                "uid": principal.user_id,
                "exp": principal.expires_at,
            },
        )


class AuthService:
    def __init__(self, settings: Settings, db: Database, gateway: SupabaseGateway):
        self.settings, self.db, self.gateway = settings, db, gateway
        self.repository = SessionRepository(db)

    def cipher(self) -> MultiFernet:
        if not self.settings.session_encryption_key:
            raise unavailable("Session encryption")
        return MultiFernet(
            [
                Fernet(k.get_secret_value().encode())
                for k in [
                    self.settings.session_encryption_key,
                    *self.settings.session_decryption_keys,
                ]
            ]
        )

    def login_web(self, email: str, password: str) -> tuple[str, str, Principal]:
        cipher = self.cipher()
        if self.db.engine is None:
            raise unavailable("Database")
        tokens = token_payload(self.gateway.login(email, password))
        principal = self.gateway.verify(tokens["access_token"])
        tokens["expires_at"] = principal.expires_at.timestamp()
        self.repository.ensure_user(principal)
        session, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        encrypted = cipher.encrypt(
            json.dumps(
                {k: tokens[k] for k in ("access_token", "refresh_token", "expires_at")}
            ).encode()
        ).decode()
        with self.db.transaction(principal.user_id) as conn:
            conn.execute(
                text("""INSERT INTO medlm_auth.web_sessions
              (id_hash,user_id,encrypted_tokens,csrf_token,expires_at,provider_session_id)
              VALUES (:id,:uid,:tokens,:csrf,:expires,:sid)"""),
                {
                    "id": digest(session),
                    "uid": principal.user_id,
                    "sid": principal.session_id,
                    "tokens": encrypted,
                    "csrf": csrf,
                    "expires": datetime.now(UTC)
                    + timedelta(seconds=self.settings.session_ttl_seconds),
                },
            )
        return session, csrf, principal

    def native(self, token: str) -> Principal:
        principal = self.gateway.verify(token)
        self.repository.ensure_user(principal)
        return principal

    def web(self, session: str, csrf: str | None = None, mutation: bool = False):
        error = None
        # Logout takes the same row lock. No provider operation can resurrect this row.
        with self.db.transaction() as conn:
            row = (
                conn.execute(
                    text("SELECT * FROM medlm_auth.web_sessions WHERE id_hash=:id FOR UPDATE"),
                    {"id": digest(session)},
                )
                .mappings()
                .first()
            )
            if not row or row["revoked_at"] or row["expires_at"] <= datetime.now(UTC):
                raise AppError(401, "invalid_session", "Sign in again.")
            if mutation and (not csrf or not secrets.compare_digest(csrf, row["csrf_token"])):
                raise AppError(403, "csrf_failed", "Request could not be verified.")
            conn.execute(
                text("SELECT set_config('app.user_id',:id,true)"), {"id": str(row["user_id"])}
            )
            binding = None
            refreshing = False
            try:
                tokens = self.decrypt(row)
                binding = self.binding(row, tokens)
                self.repository.check_access_in(conn, binding)
                refreshing = tokens["expires_at"] <= datetime.now(UTC).timestamp() + 60
                if refreshing:
                    tokens = token_payload(self.gateway.refresh(tokens["refresh_token"]))
                principal = self.gateway.verify(tokens["access_token"])
                if (principal.user_id, principal.session_id) != (
                    binding.user_id,
                    binding.session_id,
                ):
                    raise AppError(401, "invalid_session", "Sign in again.")
                if row["expires_at"] <= datetime.now(UTC):
                    raise AppError(401, "invalid_session", "Sign in again.")
                tokens["expires_at"] = principal.expires_at.timestamp()
                self.repository.check_access_in(conn, principal)
                conn.execute(
                    text("""UPDATE medlm_auth.web_sessions SET
                    encrypted_tokens=:tokens,provider_session_id=:sid WHERE id_hash=:id"""),
                    {
                        "tokens": self.cipher().encrypt(json.dumps(tokens).encode()).decode(),
                        "sid": principal.session_id,
                        "id": digest(session),
                    },
                )
            except AppError as exc:
                if exc.status != 401 and not refreshing:
                    raise
                # Commit invalidation even on uncertain remote rotation; never replay blindly.
                conn.execute(
                    text("UPDATE medlm_auth.web_sessions SET revoked_at=now() WHERE id_hash=:id"),
                    {"id": digest(session)},
                )
                if binding:
                    self.repository.revoke_in(conn, binding)
                error = exc
        if error:
            raise error
        # Request work must respect both provider and absolute browser-session expiry.
        principal = Principal(
            principal.user_id, principal.session_id, min(principal.expires_at, row["expires_at"])
        )
        return principal, row["csrf_token"], tokens["access_token"]

    def decrypt(self, row):
        try:
            return token_payload(
                json.loads(self.cipher().decrypt(row["encrypted_tokens"].encode())), stored=True
            )
        except (InvalidToken, ValueError, TypeError) as exc:
            raise AppError(401, "invalid_session", "Sign in again.") from exc

    def binding(self, row, tokens):
        if row["provider_session_id"]:
            return Principal(row["user_id"], row["provider_session_id"], row["expires_at"])
        # Legacy Phase 1 cookies: establish binding from a signed token, never a decode-only claim.
        principal = self.gateway.verify_local(tokens["access_token"], allow_expired=True)
        if principal.user_id != row["user_id"]:
            raise AppError(401, "invalid_session", "Sign in again.")
        return principal

    def logout_web(self, session: str, csrf: str | None):
        token = None
        with self.db.transaction() as conn:
            row = (
                conn.execute(
                    text("SELECT * FROM medlm_auth.web_sessions WHERE id_hash=:id FOR UPDATE"),
                    {"id": digest(session)},
                )
                .mappings()
                .first()
            )
            if row is None:
                return
            if not csrf or not secrets.compare_digest(csrf, row["csrf_token"]):
                raise AppError(403, "csrf_failed", "Request could not be verified.")
            if row["revoked_at"]:
                return
            tokens = None
            try:
                tokens = self.decrypt(row)
                token = tokens["access_token"]
            except AppError:
                if not row["provider_session_id"]:
                    raise
            principal = self.binding(row, tokens)
            # No online /user or refresh dependency: possession of cookie+CSRF is sufficient.
            self.repository.revoke_in(conn, principal)
            conn.execute(
                text("UPDATE medlm_auth.web_sessions SET revoked_at=now() WHERE id_hash=:id"),
                {"id": digest(session)},
            )
        if token:
            self.upstream_logout(token)

    def logout_native(self, token: str):
        principal = self.gateway.verify_local(token)
        with self.db.transaction(principal.user_id) as conn:
            if not conn.scalar(
                text("SELECT 1 FROM medlm.users WHERE id=:id"), {"id": principal.user_id}
            ):
                raise AppError(401, "invalid_session", "Sign in again.")
            # Match web lock ordering: rows first, revocation second.
            conn.execute(
                text("""SELECT id_hash FROM medlm_auth.web_sessions
                WHERE user_id=:uid AND provider_session_id=:sid ORDER BY id_hash FOR UPDATE"""),
                {"uid": principal.user_id, "sid": principal.session_id},
            ).all()
            self.repository.revoke_in(conn, principal)
            conn.execute(
                text("""UPDATE medlm_auth.web_sessions SET revoked_at=now()
                WHERE user_id=:uid AND provider_session_id=:sid"""),
                {"uid": principal.user_id, "sid": principal.session_id},
            )
        self.upstream_logout(token)

    def upstream_logout(self, token):
        try:
            self.gateway.logout(token)
        except AppError:
            pass

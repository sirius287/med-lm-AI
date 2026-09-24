import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import jwt
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import text

from medlm_api.config import Settings
from medlm_api.database import Database
from medlm_api.errors import AppError, unavailable


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


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
        return response.json() if response.content else {}

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

    def verify(self, token: str) -> Principal:
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
                options={"require": ["exp", "sub", "session_id", "iss", "aud"]},
            )
            principal = Principal(
                UUID(claims["sub"]),
                UUID(claims["session_id"]),
                datetime.fromtimestamp(claims["exp"], UTC),
            )
        except jwt.PyJWKClientConnectionError as exc:
            raise AppError(503, "auth_unavailable", "Authentication is unavailable.", True) from exc
        except (jwt.PyJWTError, ValueError, KeyError) as exc:
            raise AppError(401, "invalid_session", "Sign in again.") from exc
        # Online provider check in addition to local signature and revocation checks.
        user = self._request("GET", "user", token=token)
        if user.get("id") != str(principal.user_id):
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
            row = conn.execute(
                text("SELECT disabled_at FROM medlm.users WHERE id=:id"), {"id": principal.user_id}
            ).first()
            revoked = conn.scalar(
                text("SELECT 1 FROM medlm_auth.revoked_sessions WHERE session_id=:id"),
                {"id": principal.session_id},
            )
            if row is None or row.disabled_at or revoked:
                raise AppError(401, "invalid_session", "Sign in again.")

    def revoke(self, principal: Principal):
        with self.db.transaction(principal.user_id) as conn:
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

    def cipher(self) -> Fernet:
        if not self.settings.session_encryption_key:
            raise unavailable("Session encryption")
        return Fernet(self.settings.session_encryption_key.get_secret_value().encode())

    def login_web(self, email: str, password: str) -> tuple[str, str, Principal]:
        cipher = self.cipher()
        if self.db.engine is None:
            raise unavailable("Database")
        tokens = self.gateway.login(email, password)
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
              (id_hash,user_id,encrypted_tokens,csrf_token,expires_at)
              VALUES (:id,:uid,:tokens,:csrf,:expires)"""),
                {
                    "id": digest(session),
                    "uid": principal.user_id,
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
        # Row lock serializes refresh-token rotation across tabs/requests.
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
            try:
                tokens = json.loads(self.cipher().decrypt(row["encrypted_tokens"].encode()))
            except (InvalidToken, ValueError) as exc:
                raise AppError(401, "invalid_session", "Sign in again.") from exc
            if tokens["expires_at"] <= datetime.now(UTC).timestamp() + 60:
                tokens = self.gateway.refresh(tokens["refresh_token"])
                tokens["expires_at"] = self.gateway.verify(
                    tokens["access_token"]
                ).expires_at.timestamp()
                encrypted = (
                    self.cipher()
                    .encrypt(
                        json.dumps(
                            {k: tokens[k] for k in ("access_token", "refresh_token", "expires_at")}
                        ).encode()
                    )
                    .decode()
                )
                conn.execute(
                    text(
                        "UPDATE medlm_auth.web_sessions SET encrypted_tokens=:tokens WHERE id_hash=:id"
                    ),
                    {"tokens": encrypted, "id": digest(session)},
                )
            principal = self.gateway.verify(tokens["access_token"])
            if str(principal.user_id) != str(row["user_id"]):
                raise AppError(401, "invalid_session", "Sign in again.")
            self.repository.check_access(principal)
            return principal, row["csrf_token"], tokens["access_token"]

    def logout(self, principal: Principal, token: str, web_session: str | None):
        self.repository.revoke(principal)
        if web_session:
            with self.db.transaction() as conn:
                conn.execute(
                    text("UPDATE medlm_auth.web_sessions SET revoked_at=now() WHERE id_hash=:id"),
                    {"id": digest(web_session)},
                )
        # Local revocation is durable even if the upstream service is down.
        try:
            self.gateway.logout(token)
        except AppError:
            pass

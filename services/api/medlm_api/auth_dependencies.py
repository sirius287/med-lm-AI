"""Only verified principals can establish request-owned database context."""

from dataclasses import dataclass

from fastapi import Depends, Request

from medlm_api.auth import Principal, SessionRepository
from medlm_api.errors import AppError


@dataclass(frozen=True)
class AuthIdentity:
    principal: Principal
    csrf_token: str | None


def credentials(request: Request):
    header = request.headers.get("authorization")
    cookie = request.cookies.get("medlm_session")
    if header is not None and cookie is not None:
        raise AppError(400, "ambiguous_authentication", "Use one authentication method.")
    if header is not None:
        parts = header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise AppError(401, "invalid_session", "Sign in again.")
        return parts[1], None
    return None, cookie


def check_origin(request: Request):
    if request.headers.get("origin") not in request.app.state.settings.cors_origins:
        raise AppError(403, "origin_denied", "Request origin is not allowed.")


def current_identity(request: Request):
    bearer, cookie = credentials(request)
    auth = request.app.state.auth
    if bearer:
        return AuthIdentity(auth.native(bearer), None)
    if not cookie:
        raise AppError(401, "authentication_required", "Sign in to continue.")
    mutation = request.method not in ("GET", "HEAD", "OPTIONS")
    if mutation:
        check_origin(request)
    principal, csrf, _ = auth.web(cookie, request.headers.get("x-csrf-token"), mutation)
    return AuthIdentity(principal, csrf)


def owned_connection(request: Request, identity: AuthIdentity = Depends(current_identity)):
    with request.app.state.database.transaction(identity.principal.user_id) as conn:
        SessionRepository.check_access_in(conn, identity.principal)
        yield conn

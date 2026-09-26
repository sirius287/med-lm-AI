import json
import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from medlm_api.auth import AuthService, SupabaseGateway
from medlm_api.auth_dependencies import (
    check_origin,
    credentials,
    current_identity,
    owned_connection,
)
from medlm_api.auth_rate_limit import AuthRateLimiter
from medlm_api.config import Settings
from medlm_api.database import Database
from medlm_api.errors import AppError

logger = logging.getLogger("medlm")
logging.basicConfig(level=logging.INFO, format="%(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: SecretStr = Field(min_length=12, max_length=128)


class Health(BaseModel):
    status: str = "ok"
    service: str = "medlm-api"
    version: str


def create_app(settings: Settings | None = None, gateway=None) -> FastAPI:
    settings = settings or Settings()
    db = Database(settings)
    provider = gateway or SupabaseGateway(settings)
    auth = AuthService(settings, db, provider)
    limiter = AuthRateLimiter(settings, db)

    @asynccontextmanager
    async def lifespan(app):
        yield
        db.close()
        provider.close()

    app = FastAPI(title="MedLM API", version=settings.version, lifespan=lifespan)
    app.state.database, app.state.auth = db, auth
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = str(uuid4())
        started = time.monotonic()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Never log URL/query/body/header values or exception text.
        logger.info(
            json.dumps(
                {
                    "event": "request",
                    "request_id": request.state.request_id,
                    "status": response.status_code,
                    "duration_ms": round((time.monotonic() - started) * 1000),
                }
            )
        )
        return response

    def error_response(request, status, code, message, retryable=False, fields=None):
        return JSONResponse(
            status_code=status,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "retryable": retryable,
                    "field_errors": fields or [],
                },
                "request_id": request.state.request_id,
            },
            headers={"Cache-Control": "no-store", "X-Request-ID": request.state.request_id},
        )

    @app.exception_handler(AppError)
    async def app_error(request, exc):
        response = error_response(request, exc.status, exc.code, exc.message, exc.retryable)
        if exc.status == 429:
            response.headers["Retry-After"] = "60"
        if exc.status == 401 and request.cookies.get("medlm_session"):
            response.delete_cookie(
                "medlm_session",
                path="/",
                httponly=True,
                secure=settings.cookie_secure,
                samesite="lax",
            )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        fields = [{"path": ".".join(map(str, e["loc"])), "code": e["type"]} for e in exc.errors()]
        return error_response(
            request, 422, "validation_error", "Check the request fields.", fields=fields
        )

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error_response(request, exc.status_code, "http_error", "Request is unavailable.")

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        return error_response(
            request, 503, "database_unavailable", "Database is unavailable.", True
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        logger.error(
            json.dumps({"event": "internal_error", "request_id": request.state.request_id})
        )
        return error_response(request, 500, "internal_error", "The request could not be completed.")

    def limit_auth(request: Request):
        check_origin(request)
        limiter.check(request.client.host if request.client else "unknown")

    router = APIRouter(prefix=settings.api_prefix)

    @app.get("/health", response_model=Health)
    @router.get("/health", response_model=Health)
    def health():
        return Health(version=settings.version)

    @router.post("/auth/register", status_code=202, dependencies=[Depends(limit_auth)])
    def register(body: Credentials):
        provider.register(str(body.email), body.password.get_secret_value())
        return {"status": "check_email"}

    @router.post("/auth/login", dependencies=[Depends(limit_auth)])
    def login(body: Credentials, response: Response):
        session, csrf, principal = auth.login_web(str(body.email), body.password.get_secret_value())
        response.set_cookie(
            "medlm_session",
            session,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            max_age=settings.session_ttl_seconds,
            path="/",
        )
        return {"user_id": str(principal.user_id), "csrf_token": csrf}

    @router.get("/auth/session")
    def session(identity=Depends(current_identity)):
        return {"user_id": str(identity.principal.user_id), "csrf_token": identity.csrf_token}

    @router.delete("/auth/session", status_code=204)
    def logout(request: Request, response: Response):
        bearer, cookie = credentials(request)
        if bearer:
            auth.logout_native(bearer)
        else:
            check_origin(request)
            if cookie:
                auth.logout_web(cookie, request.headers.get("x-csrf-token"))
        response.delete_cookie(
            "medlm_session", path="/", httponly=True, secure=settings.cookie_secure, samesite="lax"
        )

    @router.get("/health/database")
    def database_health(connection=Depends(owned_connection)):
        from sqlalchemy import text

        connection.scalar(text("SELECT 1"))
        return {"status": "ok"}

    app.include_router(router)
    return app


app = create_app()

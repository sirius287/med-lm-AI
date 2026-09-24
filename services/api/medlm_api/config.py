from typing import Literal
from urllib.parse import urlparse

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEDLM_", env_file=".env", extra="ignore")
    environment: Literal["development", "test", "production"] = "development"
    version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    database_url: SecretStr | None = None
    supabase_url: str | None = None
    supabase_publishable_key: SecretStr | None = None
    session_encryption_key: SecretStr | None = None
    cors_origins: list[str] = ["http://localhost:8080", "http://127.0.0.1:8080"]
    cookie_secure: bool = False
    session_ttl_seconds: int = 86400
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-6-astra"
    max_image_bytes: int = 10 * 1024 * 1024
    max_image_pixels: int = 40_000_000

    @model_validator(mode="after")
    def validate_security(self):
        if self.api_prefix != "/api/v1":
            raise ValueError("The versioned API prefix must be /api/v1")
        if "*" in self.cors_origins:
            raise ValueError("Explicit CORS origins are required")
        for origin in self.cors_origins:
            parsed = urlparse(origin)
            if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.path:
                raise ValueError("CORS entries must be origins without a path")
        if self.environment == "production":
            if not self.cookie_secure or any(
                not o.startswith("https://") for o in self.cors_origins
            ):
                raise ValueError("Production requires secure cookies and HTTPS origins")
            if not all(
                (
                    self.database_url,
                    self.supabase_url,
                    self.supabase_publishable_key,
                    self.session_encryption_key,
                )
            ):
                raise ValueError("Production authentication configuration is required")
        if self.supabase_url and not self.supabase_url.startswith("https://"):
            if self.environment == "production":
                raise ValueError("Production Supabase URL must use HTTPS")
        if not 1 <= self.session_ttl_seconds <= 86400:
            raise ValueError("Session TTL must be between 1 second and 24 hours")
        return self

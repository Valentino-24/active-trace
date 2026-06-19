"""Application configuration via Pydantic Settings.

Loaded from .env file or environment variables.
Validation ensures required keys are present and meet minimum length requirements.
"""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings loaded from environment / .env file.

    Attributes:
        database_url: PostgreSQL async connection string.
        database_url_test: Test database connection string (optional).
        secret_key: Key used for JWT signing (min 32 chars).
        encryption_key: Key used for AES-256 at-rest encryption (min 32 chars).
        access_token_expire_minutes: JWT access token TTL (default 15).
        otel_service_name: OpenTelemetry service name.
        otel_exporter_otlp_endpoint: Optional OTLP exporter endpoint.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
    )

    # --- Required (no defaults) ---
    database_url: str = Field(..., alias="DATABASE_URL", min_length=1)
    database_url_test: str | None = Field(default=None, alias="DATABASE_URL_TEST")
    secret_key: str = Field(..., alias="SECRET_KEY", min_length=32)
    encryption_key: str = Field(..., alias="ENCRYPTION_KEY", min_length=32)

    # --- Optional with defaults ---
    access_token_expire_minutes: int = Field(
        default=15, alias="ACCESS_TOKEN_EXPIRE_MINUTES", ge=1
    )

    # --- SMTP (optional, for future real email sending) ---
    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int | None = Field(default=None, alias="SMTP_PORT")
    smtp_user: str | None = Field(default=None, alias="SMTP_USER")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")

    # --- Worker settings ---
    worker_poll_interval: int = Field(
        default=10, alias="WORKER_POLL_INTERVAL", ge=1
    )
    worker_batch_size: int = Field(
        default=50, alias="WORKER_BATCH_SIZE", ge=1, le=500
    )

    # --- Observability ---
    otel_service_name: str = Field(
        default="activia-trace", alias="OTEL_SERVICE_NAME"
    )
    otel_exporter_otlp_endpoint: str | None = Field(
        default=None, alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("DATABASE_URL must not be empty")
        return v

    @field_validator("secret_key", "encryption_key", mode="before")
    @classmethod
    def validate_key_length(cls, v: str, info) -> str:
        if len(v) < 32:
            raise ValueError(
                f"{info.field_name} must be at least 32 characters long"
            )
        return v

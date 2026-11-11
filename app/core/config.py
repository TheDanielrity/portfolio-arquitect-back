from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
        env_ignore_empty=True,
    )

    app_name: str = Field(default="Architecture Portfolio API", min_length=1)
    app_env: Literal["development", "test", "production"] = "development"
    debug: bool = False
    cors_origins: list[str] = Field(default_factory=list)
    database_url: SecretStr
    jwt_secret_key: SecretStr
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = Field(default=15, gt=0, le=60)
    refresh_token_expire_days: int = Field(default=7, gt=0, le=90)
    max_request_body_bytes: int = Field(default=1048576, ge=1024, le=10485760)
    auth_requests_per_minute: int = Field(default=30, ge=1, le=1000)
    contact_requests_per_minute: int = Field(default=10, ge=1, le=1000)
    storage_provider: Literal["local", "r2"] = "local"
    media_base_url: str = "http://127.0.0.1:8000"
    local_storage_path: Path = Path(".media")
    r2_account_id: str = ""
    r2_access_key_id: SecretStr = SecretStr("")
    r2_secret_access_key: SecretStr = SecretStr("")
    r2_bucket_name: str = ""
    r2_public_base_url: str = ""
    r2_presigned_url_expire_seconds: int = Field(default=300, ge=60, le=3600)
    media_cleanup_grace_seconds: int = Field(default=3600, ge=300, le=86400)
    media_max_file_size_bytes: int = Field(default=536870912, gt=0, le=5368709120)
    media_image_max_bytes: int = Field(default=20971520, gt=0)
    media_pdf_max_bytes: int = Field(default=52428800, gt=0)
    media_model_max_bytes: int = Field(default=104857600, gt=0)
    media_video_max_bytes: int = Field(default=536870912, gt=0)

    @model_validator(mode="after")
    def validate_storage(self) -> Self:
        from pydantic import TypeAdapter

        from app.core.validation import WebUrl

        TypeAdapter(WebUrl).validate_python(self.media_base_url)
        if self.r2_public_base_url:
            TypeAdapter(WebUrl).validate_python(self.r2_public_base_url)
        if self.storage_provider == "r2":
            if not all(
                (
                    self.r2_account_id,
                    self.r2_access_key_id.get_secret_value(),
                    self.r2_secret_access_key.get_secret_value(),
                    self.r2_bucket_name,
                )
            ):
                raise ValueError("R2 provider requires account, credentials and bucket")
            import re

            if not re.fullmatch(r"[a-fA-F0-9]{32}", self.r2_account_id):
                raise ValueError("R2_ACCOUNT_ID must be a 32-character account identifier")
        return self

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value()
        if len(secret.encode("utf-8")) < 32 or "CHANGE_ME" in secret.upper():
            raise ValueError("JWT_SECRET_KEY must be a random secret of at least 32 bytes")
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
            valid = (
                url.drivername == "postgresql+psycopg"
                and bool(url.host)
                and bool(url.database)
                and (url.port is None or 1 <= url.port <= 65535)
            )
        except (ArgumentError, ValueError):
            valid = False
        if not valid:
            raise ValueError(
                "DATABASE_URL must use postgresql+psycopg with a host and database name"
            ) from None
        return value

    @model_validator(mode="after")
    def validate_production(self) -> Self:
        if self.app_env == "production":
            if "*" in self.cors_origins:
                raise ValueError("Production CORS requires explicit origins")
            if self.debug:
                raise ValueError("Debug must be disabled in production")
        return self

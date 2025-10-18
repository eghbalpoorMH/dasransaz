from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"


def _split_csv(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return value
    return []


class AppSettings(BaseSettings):
    """Application configuration driven by environment variables."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = Field(default="local", alias="DJANGO_ENV")
    secret_key: str = Field(default="django-insecure-change-me", alias="DJANGO_SECRET_KEY")
    debug: bool = Field(default=False, alias="DJANGO_DEBUG")
    allowed_hosts: List[str] = Field(default_factory=list, alias="DJANGO_ALLOWED_HOSTS")
    cors_allowed_origins: List[AnyHttpUrl] = Field(default_factory=list, alias="DJANGO_CORS_ALLOWED_ORIGINS")
    csrf_trusted_origins: List[AnyHttpUrl] = Field(default_factory=list, alias="DJANGO_CSRF_TRUSTED_ORIGINS")

    database_host: str = Field(default="postgres", alias="POSTGRES_HOST")
    database_port: int = Field(default=5432, alias="POSTGRES_PORT")
    database_name: str = Field(default="storyteller", alias="POSTGRES_DB")
    database_user: str = Field(default="storyteller", alias="POSTGRES_USER")
    database_password: str = Field(default="storyteller", alias="POSTGRES_PASSWORD")

    broker_url: str = Field(default="amqp://guest:guest@rabbitmq:5672//", alias="CELERY_BROKER_URL")
    result_backend: Optional[str] = Field(default=None, alias="CELERY_RESULT_BACKEND")

    arvan_endpoint_url: AnyHttpUrl = Field(
        default="https://s3.ir-thr-at1.arvanstorage.com", alias="ARVAN_ENDPOINT_URL"
    )
    arvan_access_key_id: str = Field(default="", alias="ARVAN_ACCESS_KEY_ID")
    arvan_secret_access_key: str = Field(default="", alias="ARVAN_SECRET_ACCESS_KEY")
    arvan_static_bucket: str = Field(default="storyteller-static", alias="ARVAN_STATIC_BUCKET")
    arvan_media_bucket: str = Field(default="storyteller-media", alias="ARVAN_MEDIA_BUCKET")
    arvan_static_custom_domain: Optional[str] = Field(default=None, alias="ARVAN_STATIC_CUSTOM_DOMAIN")
    arvan_media_custom_domain: Optional[str] = Field(default=None, alias="ARVAN_MEDIA_CUSTOM_DOMAIN")
    arvan_static_location: str = Field(default="static", alias="ARVAN_STATIC_LOCATION")
    arvan_media_location: str = Field(default="media", alias="ARVAN_MEDIA_LOCATION")
    arvan_signed_url_expiry_seconds: int = Field(default=3600, alias="ARVAN_SIGNED_URL_EXPIRY_SECONDS")

    jwt_access_token_lifetime_minutes: int = Field(default=5, alias="JWT_ACCESS_TOKEN_LIFETIME_MINUTES")
    jwt_refresh_token_lifetime_days: int = Field(default=30, alias="JWT_REFRESH_TOKEN_LIFETIME_DAYS")
    jwt_rotation_strategy: str = Field(default="rotate", alias="JWT_ROTATION_STRATEGY")

    verification_code_length: int = Field(default=6, alias="AUTH_VERIFICATION_CODE_LENGTH")
    verification_code_expiry_minutes: int = Field(default=2, alias="AUTH_VERIFICATION_CODE_EXPIRY_MINUTES")
    kavenegar_api_key: str = Field(default="", alias="KAVENEGAR_API_KEY")
    kavenegar_sender: Optional[str] = Field(default=None, alias="KAVENEGAR_SENDER")
    kavenegar_template: Optional[str] = Field(default=None, alias="KAVENEGAR_TEMPLATE")

    log_level: str = Field(default="INFO", alias="DJANGO_LOG_LEVEL")

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, value: Any) -> list[str]:
        return _split_csv(value)

    @field_validator("cors_allowed_origins", "csrf_trusted_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: Any) -> list[str]:
        return _split_csv(value)


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()


settings = get_settings()

"""Application settings, loaded from environment variables (.env in dev)."""
import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "CRM Field Operations API"
    ENVIRONMENT: str = "development"  # development | staging | production
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://crm:crm@localhost:5432/crm"

    # Redis / queue
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth / JWT
    JWT_SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    # Password reset / invitations
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 60
    INVITATION_EXPIRE_HOURS: int = 72
    CUSTOMER_SIGNATURE_EXPIRE_HOURS: int = 72

    # Rate limiting (per spec section 6.1 / 6.3)
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_WINDOW_MINUTES: int = 15
    PASSWORD_RESET_MAX_PER_EMAIL_PER_HOUR: int = 3
    PASSWORD_RESET_MAX_PER_IP_PER_HOUR: int = 10

    # Plan limits (spec 5.4)
    DEFAULT_MAX_ACTIVE_USERS: int = 30

    # Frontend URL used to build reset/invitation links (never an internal host)
    FRONTEND_APP_URL: str = Field(default_factory=lambda: os.getenv("RENDER_EXTERNAL_URL", "http://localhost:5173"))

    # Email (async worker sends real email in production; dev logs to console)
    EMAIL_PROVIDER: str = "console"  # console | smtp | ses | sendgrid ...
    EMAIL_FROM: str = "no-reply@example.com"
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True

    # SMS (Masiv). Keep disabled until Masiv assigns endpoint/credentials.
    SMS_PROVIDER: str = "console"  # console | masiv
    MASIV_SMS_URL: str = ""
    MASIV_USERNAME: str = ""
    MASIV_PASSWORD: str = ""
    MASIV_SENDER: str = "PAPCRM"

    # S3 (evidence/report storage). When S3_BUCKET is empty, the evidence
    # module falls back to local disk storage under STORAGE_DIR — fine for
    # dev/demo, must be swapped for S3 (signed URLs) before production.
    S3_BUCKET: str = ""
    AWS_REGION: str = "us-east-1"
    STORAGE_DIR: str = "storage"


@lru_cache
def get_settings() -> Settings:
    return Settings()

from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    # Database
    DATABASE_URL: str

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def fix_database_url(cls, v: str) -> str:
        # Fly.io sets postgres:// but SQLAlchemy async needs postgresql+asyncpg://
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgresql://") and "+asyncpg" not in v:
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        # asyncpg doesn't accept sslmode= (psycopg2 convention); strip it
        if "sslmode=" in v:
            from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

            parsed = urlparse(v)
            params = {k: vals[0] for k, vals in parse_qs(parsed.query).items() if k != "sslmode"}
            v = urlunparse(parsed._replace(query=urlencode(params)))
        return v

    # Redis
    REDIS_URL: str

    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def fix_redis_url(cls, v: str) -> str:
        # Upstash on Fly.io uses rediss:// (TLS). redis-py's URL parser maps
        # ssl_cert_reqs via {"none": ssl.CERT_NONE, ...} — uppercase "CERT_NONE"
        # causes a KeyError. Always strip and re-add the correct lowercase value
        # so a wrongly-set Fly secret can't break auth.
        if not v.startswith("rediss://"):
            return v
        from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

        parsed = urlparse(v)
        params = {k: vs[0] for k, vs in parse_qs(parsed.query).items()}
        params["ssl_cert_reqs"] = "none"  # always correct; redis-py needs lowercase
        return urlunparse(parsed._replace(query=urlencode(params)))

    # Auth
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ADMIN_INVITE_CODE: str = (
        ""  # Required to register a new admin account; empty = feature disabled
    )

    # Storage
    CLOUDFLARE_R2_ACCOUNT_ID: str = ""
    CLOUDFLARE_R2_ACCESS_KEY_ID: str = ""
    CLOUDFLARE_R2_SECRET_ACCESS_KEY: str = ""
    CLOUDFLARE_R2_BUCKET_NAME: str = "eazzidoc-images"
    CLOUDFLARE_R2_PUBLIC_URL: str = ""

    # AI — Report Generation
    GOOGLE_API_KEY: str = ""
    GROQ_API_KEY: str = ""

    # AI — Vision
    HUGGINGFACE_API_KEY: str = ""

    # Email — Resend
    RESEND_API_KEY: str = ""
    SMTP_FROM: str = "EazziDoc <onboarding@resend.dev>"
    REPORT_EMAIL_BCC: str = ""
    FRONTEND_URL: str = "http://localhost:3000"

    # Rate limiting
    RATELIMIT_ENABLED: bool = True

    # Monitoring
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1
    SENTRY_PROFILES_SAMPLE_RATE: float = 0.0

    # Payments (Stripe)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    CONSULTATION_FEE_CENTS: int = 5000  # $50.00

    # CORS — extend via BACKEND_CORS_ORIGINS env var / Fly secret for additional origins
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "https://eazzi-doc.vercel.app",
    ]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


settings = Settings()

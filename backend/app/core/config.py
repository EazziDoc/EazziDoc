from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str

    # Auth
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

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

    # Email / SMTP
    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    REPORT_EMAIL_BCC: str = ""  # BCC address for all diagnosis-ready emails
    FRONTEND_URL: str = "http://localhost:3000"

    # Rate limiting
    RATELIMIT_ENABLED: bool = True

    # Monitoring
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1
    SENTRY_PROFILES_SAMPLE_RATE: float = 0.0

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


settings = Settings()

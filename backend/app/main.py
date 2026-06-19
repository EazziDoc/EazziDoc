from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.limiter import limiter
from app.core.logging import configure_logging
from app.middleware.request_logging import RequestIDMiddleware, RequestLoggingMiddleware


def _init_sentry() -> None:
    if not settings.SENTRY_DSN:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            integrations=[
                FastApiIntegration(),
                SqlalchemyIntegration(),
                CeleryIntegration(),
            ],
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            profiles_sample_rate=settings.SENTRY_PROFILES_SAMPLE_RATE,
            send_default_pii=False,
            environment=settings.ENVIRONMENT,
        )
    except ImportError:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_app() -> FastAPI:
    configure_logging(json_logs=settings.is_production)
    _init_sentry()

    application = FastAPI(
        title="EazziDoc API",
        description="AI-powered medical imaging diagnostic platform",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
    )

    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Middleware executes in reverse-registration order (last added = outermost)
    application.add_middleware(SlowAPIMiddleware)
    application.add_middleware(RequestLoggingMiddleware)
    application.add_middleware(RequestIDMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.api.v1.router import router as v1_router

    application.include_router(v1_router, prefix="/api/v1")

    # Expose /metrics for Prometheus scraping.
    # Exclude /metrics itself and /health from HTTP duration histograms.
    Instrumentator(
        excluded_handlers=["/metrics", "/health"],
    ).instrument(application).expose(application, include_in_schema=False)

    @application.get("/health", tags=["health"])
    async def health(db: AsyncSession = Depends(get_db)):
        db_status = "ok"
        try:
            await db.execute(text("SELECT 1"))
        except Exception:
            db_status = "error"

        overall = "ok" if db_status == "ok" else "degraded"
        return {
            "status": overall,
            "environment": settings.ENVIRONMENT,
            "checks": {"db": db_status},
        }

    return application


app = create_app()

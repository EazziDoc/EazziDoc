import ssl

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "eazzidoc",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Fly.io Upstash Redis uses rediss:// (TLS). redis-py requires explicit
# ssl_cert_reqs — without it the connection raises ValueError on task dispatch.
if settings.REDIS_URL.startswith("rediss://"):
    _ssl_opts = {"ssl_cert_reqs": ssl.CERT_NONE}
    celery_app.conf.broker_transport_options = {"ssl": _ssl_opts}
    celery_app.conf.redis_backend_use_ssl = _ssl_opts

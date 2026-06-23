import ssl

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "eazzidoc",
    broker=settings.REDIS_URL,
    # No result backend — we never read AsyncResult; task outcomes are written
    # directly to the DB by the task itself. Removing the backend halves Redis
    # connections on the free tier (20-connection Upstash limit).
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
    task_ignore_result=True,
)

# Fly.io Upstash Redis uses rediss:// (TLS).
# Belt-and-suspenders: broker_transport_options covers the initial connection;
# the REDIS_URL validator (config.py) bakes ssl_cert_reqs into the URL so
# reconnected clients (which re-parse the URL) also skip cert verification.
if settings.REDIS_URL.startswith("rediss://"):
    celery_app.conf.broker_transport_options = {
        "ssl": {"ssl_cert_reqs": ssl.CERT_NONE},
        "socket_connect_timeout": 10,
        "socket_timeout": 10,
        "socket_keepalive": True,
    }

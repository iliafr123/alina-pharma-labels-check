from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "alina_pharma",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)

import os

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Dev mode: run tasks synchronously in-process when no Redis broker is available
    task_always_eager=os.getenv("CELERY_EAGER", "false").lower() == "true",
    task_eager_propagates=True,
)

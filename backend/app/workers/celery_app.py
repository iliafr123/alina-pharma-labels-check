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
    # ack on receipt (not late): a task killed by a worker restart/crash is NOT redelivered,
    # so it cannot become a zombie that clogs the single worker's prefetch slot. For our
    # benchmarking workload, losing an interrupted task (and re-running it) is preferable to
    # an orphaned-message backlog that silently starves new checks.
    task_acks_late=False,
    worker_prefetch_multiplier=1,
    # A hung provider call must not freeze the single worker and stall the queue.
    # Soft limit raises a catchable exception (task marked FAILED); hard limit kills as backstop.
    task_soft_time_limit=240,
    task_time_limit=300,
    # Redis default visibility_timeout is 1h: a task orphaned by a worker restart
    # (e.g. redeploy) blocks the single prefetch slot for an hour. 900s > task_time_limit
    # so it redelivers orphans quickly without duplicating still-running work.
    broker_transport_options={"visibility_timeout": 900},
    result_backend_transport_options={"visibility_timeout": 900},
    # Dev mode: run tasks synchronously in-process when no Redis broker is available
    task_always_eager=os.getenv("CELERY_EAGER", "false").lower() == "true",
    task_eager_propagates=True,
)

"""Celery application configuration for RabbitMQ-backed workers."""

from celery import Celery
from celery.schedules import crontab

from settings import (
    CELERY_TASK_QUEUE,
    RABBITMQ_PREFETCH,
    RABBITMQ_URL,
)

celery_app = Celery("congress_tracker", broker=RABBITMQ_URL)
celery_app.conf.update(
    task_default_queue=CELERY_TASK_QUEUE,
    task_queues=None,
    worker_prefetch_multiplier=max(1, RABBITMQ_PREFETCH // 100),
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_ignore_result=True,
    beat_schedule={
        "daily-congress-ingest": {
            "task": "cdm.workers.tasks.schedule_daily_ingest",
            "schedule": crontab(hour=2, minute=0),
        }
    },
)

celery_app.autodiscover_tasks(["cdm.workers"])

"""Celery application configuration for RabbitMQ-backed workers."""

from datetime import timedelta

from celery import Celery
from celery.schedules import crontab

from settings import (
    CELERY_INDEX_QUEUE,
    CELERY_INGEST_QUEUE,
    CELERY_TASK_QUEUE,
    CELERY_TASK_SOFT_TIME_LIMIT,
    CELERY_TASK_TIME_LIMIT,
    RABBITMQ_PREFETCH,
    RABBITMQ_URL,
)

celery_app = Celery("congress_tracker", broker=RABBITMQ_URL)
celery_app.conf.update(
    task_default_queue=CELERY_TASK_QUEUE,
    task_routes={
        "cdm.workers.tasks.run_ingest_job": {"queue": CELERY_INGEST_QUEUE},
        "cdm.workers.tasks.run_index_job": {"queue": CELERY_INDEX_QUEUE},
        "cdm.workers.tasks.schedule_daily_ingest": {"queue": CELERY_INGEST_QUEUE},
        "cdm.workers.tasks.schedule_coverage_gaps": {"queue": CELERY_INGEST_QUEUE},
        "cdm.workers.tasks.recover_failed_ingest_jobs": {"queue": CELERY_INGEST_QUEUE},
    },
    task_queues=None,
    worker_prefetch_multiplier=max(1, RABBITMQ_PREFETCH // 100),
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_ignore_result=True,
    task_soft_time_limit=CELERY_TASK_SOFT_TIME_LIMIT,
    task_time_limit=CELERY_TASK_TIME_LIMIT,
    beat_schedule={
        "daily-congress-ingest": {
            "task": "cdm.workers.tasks.schedule_daily_ingest",
            "schedule": crontab(hour=2, minute=0),
        },
        "coverage-gap-ingest": {
            "task": "cdm.workers.tasks.schedule_coverage_gaps",
            "schedule": timedelta(hours=24),
        },
        "recover-failed-ingest-jobs": {
            "task": "cdm.workers.tasks.recover_failed_ingest_jobs",
            "schedule": crontab(minute="*/10"),
        },
    },
)

celery_app.autodiscover_tasks(["cdm.workers"])

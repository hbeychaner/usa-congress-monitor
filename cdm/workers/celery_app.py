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
        "cdm.workers.tasks.schedule_static_refresh": {"queue": CELERY_INGEST_QUEUE},
        "cdm.workers.tasks.schedule_govinfo_refresh": {"queue": CELERY_INGEST_QUEUE},
        "cdm.workers.tasks.schedule_topic_training": {"queue": CELERY_INGEST_QUEUE},
        "cdm.workers.tasks.schedule_vote_refresh": {"queue": CELERY_INGEST_QUEUE},
        "cdm.workers.tasks.schedule_member_graph_build": {"queue": CELERY_INGEST_QUEUE},
        "cdm.workers.tasks.recover_failed_ingest_jobs": {"queue": CELERY_INGEST_QUEUE},
        "cdm.workers.tasks.run_retention_maintenance": {"queue": CELERY_INGEST_QUEUE},
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
            "schedule": timedelta(hours=6),
        },
        "recover-failed-ingest-jobs": {
            "task": "cdm.workers.tasks.recover_failed_ingest_jobs",
            "schedule": crontab(minute="*/5"),
        },
        "static-resource-refresh": {
            "task": "cdm.workers.tasks.schedule_static_refresh",
            "schedule": crontab(hour=4, minute=0, day_of_week="sunday"),
        },
        "govinfo-refresh": {
            "task": "cdm.workers.tasks.schedule_govinfo_refresh",
            "schedule": crontab(hour=5, minute=0),
        },
        "vote-refresh": {
            "task": "cdm.workers.tasks.schedule_vote_refresh",
            "schedule": crontab(hour=4, minute=30),
        },
        "topic-model-retrain": {
            "task": "cdm.workers.tasks.schedule_topic_training",
            "schedule": crontab(hour=6, minute=0, day_of_week="sunday"),
        },
        "member-graph-build": {
            "task": "cdm.workers.tasks.schedule_member_graph_build",
            "schedule": crontab(hour=5, minute=0, day_of_week="monday"),
        },
        "retention-maintenance": {
            "task": "cdm.workers.tasks.run_retention_maintenance",
            "schedule": crontab(hour=3, minute=30),
        },
    },
)

celery_app.autodiscover_tasks(["cdm.workers"])

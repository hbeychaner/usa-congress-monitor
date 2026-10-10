"""Celery application configuration for RabbitMQ-backed workers."""

from datetime import timedelta

from celery import Celery
from celery.schedules import crontab

from cdm.config import get_config

celery_app = Celery("congress_tracker", broker=get_config().queue.rabbitmq_url)
celery_app.conf.update(
    task_default_queue=get_config().queue.celery_task_queue,
    task_routes={
        "cdm.workers.tasks.run_ingest_job": {"queue": get_config().queue.celery_ingest_queue},
        "cdm.workers.tasks.run_index_job": {"queue": get_config().queue.celery_index_queue},
        "cdm.workers.tasks.schedule_daily_ingest": {"queue": get_config().queue.celery_ingest_queue},
        "cdm.workers.tasks.schedule_coverage_gaps": {"queue": get_config().queue.celery_ingest_queue},
        "cdm.workers.tasks.schedule_static_refresh": {"queue": get_config().queue.celery_ingest_queue},
        "cdm.workers.tasks.schedule_govinfo_refresh": {"queue": get_config().queue.celery_ingest_queue},
        "cdm.workers.tasks.schedule_topic_training": {"queue": get_config().queue.celery_ingest_queue},
        "cdm.workers.tasks.schedule_vote_refresh": {"queue": get_config().queue.celery_ingest_queue},
        "cdm.workers.tasks.schedule_member_graph_build": {"queue": get_config().queue.celery_ingest_queue},
        "cdm.workers.tasks.trim_logs": {"queue": get_config().queue.celery_ingest_queue},
        "cdm.workers.tasks.recover_failed_ingest_jobs": {"queue": get_config().queue.celery_ingest_queue},
        "cdm.workers.tasks.run_retention_maintenance": {"queue": get_config().queue.celery_ingest_queue},
    },
    task_queues=None,
    worker_prefetch_multiplier=max(1, get_config().queue.rabbitmq_prefetch // 100),
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_ignore_result=True,
    task_soft_time_limit=get_config().queue.celery_task_soft_time_limit,
    task_time_limit=get_config().queue.celery_task_time_limit,
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
        "trim-logs": {
            "task": "cdm.workers.tasks.trim_logs",
            "schedule": crontab(minute=15),
        },
        "retention-maintenance": {
            "task": "cdm.workers.tasks.run_retention_maintenance",
            "schedule": crontab(hour=3, minute=30),
        },
    },
)

celery_app.autodiscover_tasks(["cdm.workers"])

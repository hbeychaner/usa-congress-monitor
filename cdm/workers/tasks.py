"""Thin Celery wrappers around durable ingest and indexing services."""

from __future__ import annotations

import gc
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import NoReturn

from celery.signals import worker_init
from celery.worker.worker import WorkController

from cdm.config import get_config
from cdm.ingest.voteview import VoteIngestor, VoteviewClient, current_congress
from cdm.jobs.analytics import GraphRequest, PerspectiveRequest, TopicRequest
from cdm.jobs.store import JobKind
from cdm.utils.json_types import JsonObject
from cdm.utils.lemmatize import warm_lemmatizer
from cdm.utils.log_trimmer import LogTrimmer
from cdm.workers.celery_app import celery_app
from cdm.workers.dispatch import TaskModule, TaskName
from cdm.workers.operations import OperationsContainer
from cdm.workers.results import JobResult

VOTEVIEW_DIR = Path("data/voteview")


# Worker-wide composition root; shares one set of clients across tasks.
@lru_cache(maxsize=1)
def _container() -> OperationsContainer:
    return OperationsContainer(get_config())


@worker_init.connect
def warm_store(sender: WorkController | None = None, **_: object) -> None:
    """Warm the store/NLP and preserve indexing parent pages before fork."""
    app = sender.app if sender is not None else None
    if (
        app is not None
        and get_config().queue.celery_analytics_queue in app.amqp.queues.consume_from
    ):
        app.loader.import_task_module(TaskModule.ANALYTICS.value)
    _container().job_store.repair_legacy_windows()
    if (
        app is not None
        and get_config().queue.celery_index_queue in app.amqp.queues.consume_from
    ):
        warm_lemmatizer()
        gc.collect()
        # Child collections must not copy the long-lived parent model/import graph.
        gc.freeze()
        logging.getLogger(__name__).info(
            "Frozen %s parent objects before indexing worker fork",
            gc.get_freeze_count(),
        )


def _execute(
    task: object, job_id: str, run: Callable[[str], JobResult],
    container: OperationsContainer | None = None,
) -> JsonObject:
    """Run a job and hand failures to the retry policy."""
    try:
        with (container if container is not None else _container()).job_heartbeat.watch(job_id):
            return run(job_id).model_dump(mode="json", exclude_none=True)
    except Exception as exc:  # noqa: BLE001 - Celery must retry all ordinary task failures.
        _retry(task, job_id, exc, container)


def _retry(
    task: object, job_id: str, exc: Exception, container: OperationsContainer | None = None,
) -> NoReturn:
    (container if container is not None else _container()).task_retrier.handle(
        task,  # type: ignore[arg-type]
        job_id, exc,
    )


@celery_app.task(
    bind=True,
    name=TaskName.RUN_INGEST.value,
    soft_time_limit=get_config().queue.celery_ingest_soft_time_limit,
    time_limit=get_config().queue.celery_ingest_time_limit,
)
def run_ingest_job(self: object, job_id: str) -> JsonObject:
    return _execute(self, job_id, _container().ingest_runner.run)


@celery_app.task(bind=True, name=TaskName.RUN_GOVINFO_BULK.value)
def run_govinfo_bulk_job(self: object, job_id: str) -> JsonObject:
    """Run one durable GovInfo package job."""
    return _execute(self, job_id, _container().govinfo_package_runner.run)


@celery_app.task(bind=True, name=TaskName.RUN_GOVINFO_BATCH.value)
def run_govinfo_bulk_batch(self: object, batch_id: str) -> JsonObject:
    """Fan out a durable batch into independently retryable package tasks."""
    return _execute(self, batch_id, _container().govinfo_batch_runner.run)


@celery_app.task(bind=True, name=TaskName.RUN_INDEX.value)
def run_index_job(self: object, job_id: str) -> JsonObject:
    return _execute(self, job_id, _container().index_runner.run)


@celery_app.task(bind=True, name=TaskName.RUN_RECONCILIATION.value)
def run_reconciliation_job(self: object, job_id: str) -> JsonObject:
    """Replay archived GovInfo records into a validated staging index."""
    return _execute(self, job_id, _container().reconciliation_runner.run)


@celery_app.task(name="cdm.workers.tasks.schedule_daily_ingest")
def schedule_daily_ingest() -> JsonObject:
    container = _container()
    payload = container.daily_ingest_planner.payload(datetime.now(UTC).date())
    job = container.job_submitter.submit(JobKind.INGEST.value, payload.to_json())
    return {"job_id": job["id"], "status": job["status"]}


@celery_app.task(name="cdm.workers.tasks.schedule_coverage_gaps")
def schedule_coverage_gaps() -> JsonObject:
    """Queue idempotent jobs for date-windowed coverage gaps over 24 hours."""
    container = _container()
    queued = [
        container.job_submitter.submit(
            JobKind.INGEST.value, payload.to_json(), dispatch_existing=False
        )["id"]
        for payload in container.coverage_gap_planner.payloads()
    ]
    return {"queued": queued, "count": len(queued)}


@celery_app.task(name="cdm.workers.tasks.schedule_static_refresh")
def schedule_static_refresh() -> JsonObject:
    container = _container()
    queued = [
        container.job_submitter.submit(JobKind.INGEST.value, payload.to_json())["id"]
        for payload in container.static_refresh_planner.payloads(
            datetime.now(UTC).date()
        )
    ]
    return {"queued": queued, "count": len(queued)}


@celery_app.task(name="cdm.workers.tasks.schedule_topic_training")
def schedule_topic_training() -> JsonObject:
    """Start a topic-model retrain unless one is already running."""
    return _container().analytics_jobs.submit(TopicRequest()).model_dump(mode="json")


@celery_app.task(name="cdm.workers.tasks.schedule_member_graph_build")
def schedule_member_graph_build() -> JsonObject:
    """Start a member graph rebuild unless one is already running."""
    return _container().analytics_jobs.submit(GraphRequest()).model_dump(mode="json")


@celery_app.task(name="cdm.workers.tasks.schedule_perspective_build")
def schedule_perspective_build() -> JsonObject:
    """Rebuild the current Congress's party perspectives unless a build is running."""
    return (
        _container()
        .analytics_jobs.submit(PerspectiveRequest(top_topics=None))
        .model_dump(mode="json")
    )


@celery_app.task(name="cdm.workers.tasks.schedule_vote_refresh")
def schedule_vote_refresh() -> JsonObject:
    """Refresh roll calls (both chambers) for the current Congress."""
    congress = current_congress(datetime.now(UTC).year)
    ingestor = VoteIngestor(_container().elastic_client, VoteviewClient(VOTEVIEW_DIR))
    return {
        "congress": congress,
        "roll_calls": ingestor.ingest_congress(congress, refresh=True),
    }


@celery_app.task(name="cdm.workers.tasks.schedule_govinfo_refresh")
def schedule_govinfo_refresh() -> JsonObject:
    """Queue GovInfo packages for the current Congress that have no job yet."""
    congress, queued = _container().govinfo_refresh_scheduler.run(datetime.now(UTC))
    return {"congress": congress, "queued": len(queued)}


@celery_app.task(name="cdm.workers.tasks.recover_failed_ingest_jobs")
def recover_failed_ingest_jobs() -> JsonObject:
    """Requeue jobs stranded by a worker crash and redispatch rare orphaned jobs."""
    result = _container().recovery_service.recover()
    return result.model_dump(mode="json", exclude_none=True)


@celery_app.task(name="cdm.workers.tasks.trim_logs")
def trim_logs() -> JsonObject:
    """Cap every log file at its newest lines."""
    trimmed = LogTrimmer().trim_all()
    return {"trimmed": [result.model_dump() for result in trimmed]}


@celery_app.task(name="cdm.workers.tasks.run_retention_maintenance")
def run_retention_maintenance() -> JsonObject:
    """Prune old terminal jobs and their Redis streams and archive directories."""
    return _container().retention_service.run().model_dump(mode="json")

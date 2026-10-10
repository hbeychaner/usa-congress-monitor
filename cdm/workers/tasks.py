"""Thin Celery wrappers around durable ingest and indexing services."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import NoReturn

from celery.signals import worker_init

from cdm.config import get_config
from cdm.graph.runner import GraphBuildRunner
from cdm.ingest.voteview import VoteIngestor, VoteviewClient, current_congress
from cdm.jobs.store import JobKind
from cdm.utils.json_types import JsonObject
from cdm.utils.log_trimmer import LogTrimmer
from cdm.utils.topic_training import start_training
from cdm.workers.celery_app import celery_app
from cdm.workers.dispatch import TaskName
from cdm.workers.results import JobResult
from cdm.workers.runtime import WorkerContainer

VOTEVIEW_DIR = Path("data/voteview")


# Worker-wide composition root; shares one set of clients across tasks.
@lru_cache(maxsize=1)
def _container() -> WorkerContainer:
    return WorkerContainer(get_config())


@worker_init.connect
def warm_store(**_: object) -> None:
    """Build the store in the parent so forked children inherit it."""
    _container().job_store.repair_legacy_windows()


def _execute(task: object, job_id: str, run: Callable[[str], JobResult]) -> JsonObject:
    """Run a job and hand failures to the retry policy."""
    try:
        return run(job_id).model_dump(mode="json", exclude_none=True)
    except Exception as exc:  # noqa: BLE001 - Celery must retry all ordinary task failures.
        _retry(task, job_id, exc)


def _retry(task: object, job_id: str, exc: Exception) -> NoReturn:
    _container().task_retrier.handle(task, job_id, exc)  # type: ignore[arg-type]


@celery_app.task(bind=True, name=TaskName.RUN_INGEST.value)
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
        container.job_submitter.submit(JobKind.INGEST.value, payload.to_json())["id"]
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
    status = start_training()
    return {"started": status.started, "state": status.state.value}


@celery_app.task(name="cdm.workers.tasks.schedule_member_graph_build")
def schedule_member_graph_build() -> JsonObject:
    """Start a member graph rebuild unless one is already running."""
    status = GraphBuildRunner().start()
    return {"started": status.started, "state": status.state.value}


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

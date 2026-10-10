"""Job submission and broker dispatch."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum

from celery import Celery

from cdm.config.app_config import QueueConfig
from cdm.jobs.store import JobKind, JobRow, JobStatus, JobStore
from cdm.utils.json_types import JsonObject


class TaskName(StrEnum):
    RUN_INGEST = "cdm.workers.tasks.run_ingest_job"
    RUN_INDEX = "cdm.workers.tasks.run_index_job"
    RUN_GOVINFO_BULK = "cdm.workers.tasks.run_govinfo_bulk_job"
    RUN_GOVINFO_BATCH = "cdm.workers.tasks.run_govinfo_bulk_batch"
    RUN_RECONCILIATION = "cdm.workers.tasks.run_reconciliation_job"


class JobDispatcher:
    """Routes a ledger job to its Celery task and queue."""

    def __init__(self, app: Celery, queues: QueueConfig) -> None:
        self._app = app
        self._routes: dict[JobKind, tuple[TaskName, str]] = {
            JobKind.INGEST: (TaskName.RUN_INGEST, queues.celery_ingest_queue),
            JobKind.INDEX: (TaskName.RUN_INDEX, queues.celery_index_queue),
            JobKind.GOVINFO_BULK: (
                TaskName.RUN_GOVINFO_BULK,
                queues.celery_bulk_queue,
            ),
            JobKind.GOVINFO_BULK_BATCH: (
                TaskName.RUN_GOVINFO_BATCH,
                queues.celery_bulk_queue,
            ),
            JobKind.RECONCILE: (
                TaskName.RUN_RECONCILIATION,
                queues.celery_index_queue,
            ),
        }

    def dispatch(self, kind: str, job_id: str) -> None:
        try:
            route = self._routes.get(JobKind(kind))
        except ValueError:
            return
        if route is not None:
            name, queue = route
            self._app.send_task(name.value, args=[job_id], queue=queue)


class JobSubmitter:
    """Creates idempotent ledger jobs and dispatches the ones that need work."""

    def __init__(self, store: JobStore, dispatcher: JobDispatcher) -> None:
        self._store = store
        self._dispatcher = dispatcher

    @staticmethod
    def job_id(kind: str, payload: JsonObject) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(encoded.encode()).hexdigest()[:24]
        return f"{kind}:{digest}"

    def exists(self, kind: str, payload: JsonObject) -> bool:
        try:
            self._store.get(self.job_id(kind, payload))
        except KeyError:
            return False
        return True

    def submit(
        self,
        kind: str,
        payload: JsonObject,
        *,
        dispatch_existing: bool = True,
        dispatch: bool = True,
    ) -> JobRow:
        job_id = self.job_id(kind, payload)
        existing: JobRow | None = None
        if not dispatch_existing:
            try:
                existing = self._store.get(job_id)
            except KeyError:
                pass
        job = self._store.create(kind, job_id, payload)
        should_dispatch = dispatch and (
            existing is None or job["status"] == JobStatus.FAILED
        )
        if should_dispatch and job["status"] in {JobStatus.QUEUED, JobStatus.FAILED}:
            self._dispatcher.dispatch(kind, job_id)
        return job

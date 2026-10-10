"""Result and retry primitives shared by worker task runners."""

from __future__ import annotations

from typing import NoReturn, Protocol

from celery.exceptions import MaxRetriesExceededError
from pydantic import BaseModel, ConfigDict

from cdm.config.app_config import QueueConfig
from cdm.jobs.store import JobStore
from cdm.workers.failures import FailureClassifier


class JobResult(BaseModel):
    """JSON-serializable task return value; unset fields are omitted."""

    model_config = ConfigDict(extra="allow")

    job_id: str | None = None
    skipped: bool | None = None
    status: str | None = None
    cancelled: bool | None = None
    index_jobs: list[str] | None = None
    resource: str | None = None
    packages_dispatched: list[str] | None = None
    batched_jobs: int | None = None


class RetryableTask(Protocol):
    """The slice of a bound Celery task used to schedule a retry."""

    class _Request(Protocol):
        retries: int

    request: _Request

    def retry(
        self,
        *,
        exc: BaseException,
        countdown: int,
        max_retries: int,
    ) -> BaseException: ...


class TaskRetrier:
    """Marks failures in the ledger and schedules retries for transient ones."""

    def __init__(
        self,
        store: JobStore,
        queues: QueueConfig,
        classifier: FailureClassifier,
    ) -> None:
        self._store = store
        self._queues = queues
        self._classifier = classifier

    def handle(self, task: RetryableTask, job_id: str, exc: Exception) -> NoReturn:
        if not self._classifier.is_transient(exc):
            self._store.mark_failed(job_id, str(exc))
            raise exc
        self._store.mark_retrying(job_id, str(exc))
        try:
            raise task.retry(
                exc=exc,
                countdown=min(
                    self._queues.celery_retry_backoff_max,
                    2 ** min(task.request.retries, 10),
                ),
                max_retries=self._queues.celery_retry_max_transient,
            )
        except MaxRetriesExceededError:
            self._store.mark_failed(job_id, str(exc))
            raise


class SkippedClaim:
    """Builds the result for a job another worker already claimed."""

    def __init__(self, store: JobStore) -> None:
        self._store = store

    def result(self, job_id: str) -> JobResult:
        existing = self._store.get(job_id)
        return JobResult(job_id=job_id, skipped=True, status=existing["status"])

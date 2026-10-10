"""Periodic maintenance: crash recovery, retention, and GovInfo discovery."""

from __future__ import annotations

import logging
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from celery import Celery
from pydantic import BaseModel
from redis import Redis

from cdm.config.app_config import GovInfoConfig, LedgerConfig, QueueConfig
from cdm.ingest.govinfo import GovInfoDiscovery
from cdm.jobs.payloads import GovInfoPackagePayload
from cdm.jobs.store import JobKind, JobRow, JobStatus, JobStore
from cdm.utils.archive_sweeper import OrphanArchiveSweeper
from cdm.workers.dispatch import JobDispatcher, JobSubmitter
from cdm.workers.failures import FailureClassifier
from cdm.workers.planners import congress_for_year

logger = logging.getLogger(__name__)


class QueueDepthProbe:
    """Reads broker queue depth."""

    def __init__(self, app: Celery) -> None:
        self._app = app

    def depth(self, queue: str) -> int | None:
        """Broker message count for *queue*, or None if unavailable."""
        try:
            with self._app.connection_for_read() as connection:
                channel = connection.default_channel
                return int(
                    channel.queue_declare(queue=queue, passive=True).message_count
                )
        except Exception:
            logger.warning("Could not read depth of queue %s", queue, exc_info=True)
            return None


class RecoveryResult(BaseModel):
    recovered: list[str]
    skipped: str | None = None


class JobRecoveryService:
    """Requeues jobs stranded by a worker crash and redispatches orphaned jobs.

    Crash recovery (RUNNING/RETRYING jobs whose worker died) runs every tick.
    Redispatching QUEUED jobs is capped and uses a staleness window since a
    normal queued job already has a message sitting in the broker. Ingest jobs
    use a longer window because historical jobs can legitimately wait for a
    day; this still repairs rows whose broker delivery was lost.
    """

    LOCK_NAME = "congress:workers:recover_failed_ingest_jobs"
    LOCK_TIMEOUT_SECONDS = 3600
    # Redispatching an already-QUEUED job is a rare safety net for messages
    # lost to broker hiccups, not a routine driver of work.
    CRASH_CUTOFF = timedelta(minutes=15)
    ORPHAN_CUTOFF = timedelta(minutes=60)
    INGEST_ORPHAN_CUTOFF = timedelta(days=1)
    ORPHAN_BATCH_LIMIT = 25
    ORPHAN_KINDS = (JobKind.GOVINFO_BULK.value, JobKind.GOVINFO_BULK_BATCH.value)
    # Index jobs are re-sent only when the broker queue is nearly empty,
    # topping it up to the high watermark.
    INDEX_LOW_WATERMARK = 500
    INDEX_HIGH_WATERMARK = 2000
    INDEX_QUEUED_CUTOFF = timedelta(minutes=5)
    ACTIVE_BATCH_STATUSES = frozenset({
        JobStatus.QUEUED,
        JobStatus.RUNNING,
        JobStatus.RETRYING,
    })

    def __init__(
        self,
        store: JobStore,
        redis_client: Redis,
        dispatcher: JobDispatcher,
        probe: QueueDepthProbe,
        classifier: FailureClassifier,
        queues: QueueConfig,
    ) -> None:
        self._store = store
        self._redis = redis_client
        self._dispatcher = dispatcher
        self._probe = probe
        self._classifier = classifier
        self._queues = queues

    def index_redispatch_budget(self) -> int:
        depth = self._probe.depth(self._queues.celery_index_queue)
        if depth is None or depth >= self.INDEX_LOW_WATERMARK:
            return 0
        return self.INDEX_HIGH_WATERMARK - depth

    def recover(self) -> RecoveryResult:
        lock = self._redis.lock(
            self.LOCK_NAME, timeout=self.LOCK_TIMEOUT_SECONDS, blocking=False
        )
        if not lock.acquire():
            return RecoveryResult(recovered=[], skipped="already_running")
        try:
            return RecoveryResult(recovered=self._requeue(self._candidates()))
        finally:
            lock.release()

    def _candidates(self) -> list[JobRow]:
        now = datetime.now(UTC)
        store = self._store
        candidates = [
            *store.failed(),
            *store.stale_active((now - self.CRASH_CUTOFF).isoformat()),
            *store.stale_queued(
                self.ORPHAN_KINDS,
                (now - self.ORPHAN_CUTOFF).isoformat(),
                self.ORPHAN_BATCH_LIMIT,
            ),
            *store.stale_queued(
                (JobKind.INGEST.value,),
                (now - self.INGEST_ORPHAN_CUTOFF).isoformat(),
                self.ORPHAN_BATCH_LIMIT,
            ),
        ]
        budget = self.index_redispatch_budget()
        if budget:
            candidates.extend(
                store.stale_queued(
                    (JobKind.INDEX.value,),
                    (now - self.INDEX_QUEUED_CUTOFF).isoformat(),
                    budget,
                )
            )
        return candidates

    def _batched_package_ids(self) -> set[str]:
        ids: set[str] = set()
        for batch in self._store.jobs(JobKind.GOVINFO_BULK_BATCH.value):
            if batch["status"] in self.ACTIVE_BATCH_STATUSES:
                job_ids = batch["payload"].get("job_ids", [])
                if isinstance(job_ids, list):
                    ids.update(str(job_id) for job_id in job_ids)
        return ids

    def _requeue(self, candidates: list[JobRow]) -> list[str]:
        batched = self._batched_package_ids()
        recovered: list[str] = []
        seen: set[str] = set()
        for job in candidates:
            if job["id"] in seen:
                continue
            seen.add(job["id"])
            if job["kind"] == JobKind.GOVINFO_BULK and job["id"] in batched:
                continue
            if job["status"] == JobStatus.FAILED and not (
                self._classifier.is_retryable_error(job["last_error"])
            ):
                continue
            requeued = self._store.requeue(job["id"])
            self._dispatcher.dispatch(job["kind"], requeued["id"])
            recovered.append(requeued["id"])
        return recovered


class RetentionResult(BaseModel):
    pruned_jobs: int
    streams_deleted: int
    archives_deleted: int
    orphan_archives_deleted: int
    orphan_bytes_freed: int
    vacuumed: bool
    protected: list[str]


class RetentionService:
    """Prunes old terminal jobs and their Redis streams and archive directories.

    Coverage history (``ingest_windows``) is preserved so gap scheduling and
    future historical backfills still see what was ingested. Jobs whose
    streams or archives are still referenced by an unfinished index job are
    protected until that index job resolves.
    """

    STREAM_PREFIX = "congress:ingest:"
    ARCHIVED_KINDS = frozenset({JobKind.INGEST.value, JobKind.GOVINFO_BULK.value})

    def __init__(
        self,
        store: JobStore,
        redis_client: Redis,
        ledger: LedgerConfig,
        govinfo: GovInfoConfig,
        data_root: Path = Path("data"),
    ) -> None:
        self._store = store
        self._redis = redis_client
        self._ledger = ledger
        self._govinfo = govinfo
        self._data_root = data_root

    @classmethod
    def stream_source_job_id(cls, stream_name: str) -> str | None:
        """Extract the ingest job id from ``congress:ingest:<job_id>:<resource>``."""
        if not stream_name.startswith(cls.STREAM_PREFIX):
            return None
        remainder = stream_name[len(cls.STREAM_PREFIX) :]
        job_id, _, _resource = remainder.rpartition(":")
        return job_id or None

    def run(self) -> RetentionResult:
        store = self._store
        cutoff = (
            datetime.now(UTC) - timedelta(days=self._ledger.retention_days)
        ).isoformat()
        protected = self._protected_job_ids()
        pruned = store.prune_terminal_jobs(older_than=cutoff, exclude_ids=protected)
        streams_deleted = self._delete_streams(protected, {job["id"] for job in pruned})
        archives_deleted = self._delete_archives(pruned)
        # Directories left behind by jobs pruned before archive cleanup covered them.
        orphan_sweep = OrphanArchiveSweeper(
            self._govinfo.govinfo_archive_root, f"{JobKind.GOVINFO_BULK.value}:"
        ).sweep(store.all_ids())
        vacuumed = store.vacuum() if pruned else False
        store.checkpoint_wal()
        return RetentionResult(
            pruned_jobs=len(pruned),
            streams_deleted=streams_deleted,
            archives_deleted=archives_deleted,
            orphan_archives_deleted=orphan_sweep.directories_removed,
            orphan_bytes_freed=orphan_sweep.bytes_freed,
            vacuumed=vacuumed,
            protected=sorted(protected),
        )

    def _protected_job_ids(self) -> set[str]:
        protected: set[str] = set()
        for job in self._store.unfinished(JobKind.INDEX.value):
            source_id = self.stream_source_job_id(str(job["payload"].get("stream", "")))
            if source_id:
                protected.add(source_id)
        return protected

    def _delete_streams(self, protected: set[str], pruned_ids: set[str]) -> int:
        # Streams are only a transport between ingest and indexing; once the
        # source job is terminal (and no unfinished index job references it) the
        # per-job archive is the durable replay source, so delete streams
        # immediately instead of waiting out the ledger retention window.
        existing_ids = self._store.all_ids()
        terminal_ids = self._store.ids_with_status((
            JobStatus.SUCCEEDED.value,
            JobStatus.CANCELLED.value,
        ))
        deleted = 0
        for key in self._redis.scan_iter(match=f"{self.STREAM_PREFIX}*", count=1000):
            name = key.decode() if isinstance(key, bytes) else str(key)
            source_id = self.stream_source_job_id(name)
            if source_id is None or source_id in protected:
                continue
            if source_id in pruned_ids or source_id in terminal_ids:
                self._redis.delete(key)
                deleted += 1
            elif source_id not in existing_ids and not self._exists(source_id):
                # Re-check the ledger: a job created after the snapshot must
                # not have its fresh stream deleted as an orphan.
                self._redis.delete(key)
                deleted += 1
        return deleted

    def _exists(self, job_id: str) -> bool:
        try:
            self._store.get(job_id)
        except KeyError:
            return False
        return True

    def _delete_archives(self, pruned: list[JobRow]) -> int:
        # Per-job archive directories were the resume/replay source and are no
        # longer needed once indexing is settled.
        root = self._data_root.resolve()
        deleted = 0
        for job in pruned:
            if job["kind"] not in self.ARCHIVED_KINDS:
                continue
            outdir = job["payload"].get("outdir")
            if not outdir:
                continue
            job_dir = (Path(str(outdir)) / job["id"]).resolve()
            if job_dir.is_dir() and job_dir.is_relative_to(root):
                shutil.rmtree(job_dir, ignore_errors=True)
                deleted += 1
        return deleted


class GovInfoRefreshScheduler:
    """Queues GovInfo packages for the current Congress that have no job yet."""

    OUTDIR = "data/full_history/govinfo"

    def __init__(
        self,
        submitter: JobSubmitter,
        discovery: GovInfoDiscovery,
    ) -> None:
        self._submitter = submitter
        self._discovery = discovery

    def run(self, now: datetime) -> tuple[int, list[str]]:
        congress = congress_for_year(now.year)
        queued: list[str] = []
        for package in self._discovery.list_congress_packages(congress):
            payload = GovInfoPackagePayload(
                collection=package.collection,
                congress=package.congress,
                measure_type=package.measure_type,
                package_id=package.package_id,
                url=package.url,
                session=package.session,
                version_code=package.version_code,
                outdir=self.OUTDIR,
                target_index=None,
                replace=False,
            ).to_json()
            if self._submitter.exists(JobKind.GOVINFO_BULK.value, payload):
                continue
            queued.append(self._submitter.submit(JobKind.GOVINFO_BULK.value, payload)["id"])
        return congress, queued

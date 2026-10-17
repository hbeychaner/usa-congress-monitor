"""Runs one durable ingest job: pipeline -> Redis streams -> index jobs."""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from redis import Redis

from cdm.config.app_config import CongressApiConfig, QueueConfig, RedisConfig
from cdm.ingest.archive import (
    JsonlRecordArchive,
    LatestRecordArchive,
    SQLiteQuarantineArchive,
)
from cdm.ingest.pipeline import Pipeline, PipelineConfig, ResourceResult
from cdm.ingest.record_library import RecordLibrary
from cdm.ingest.redis_stream import RedisRecordStream
from cdm.ingest.runner import IngestCancelledError, Resource
from cdm.ingest.stale_bills import IndexedBillStateReader, StaleBillFilter
from cdm.jobs.payloads import IndexPayload, IngestPayload
from cdm.jobs.store import CoverageStage, JobKind, JobSlotsBusy, JobStatus, JobStore
from cdm.utils.json_types import JsonObject
from cdm.utils.rate_limiter import TokenBucket
from cdm.workers.dispatch import JobDispatcher, JobSubmitter
from cdm.workers.results import JobResult, SkippedClaim


class IngestSession:
    """Sinks the pipeline writes through for a single job attempt."""

    # Seconds between ledger status polls inside the progress callback.
    CANCEL_POLL_INTERVAL = 60.0

    def __init__(
        self,
        job_id: str,
        store: JobStore,
        redis_client: Redis,
        redis_config: RedisConfig,
        archive: JsonlRecordArchive,
        quarantine: SQLiteQuarantineArchive,
        library: LatestRecordArchive | None = None,
        flush_every: int = 100,
        on_flush: Callable[[str, int], str | None] | None = None,
    ) -> None:
        self._job_id = job_id
        self._store = store
        self._redis = redis_client
        self._redis_config = redis_config
        self.archive = archive
        self._quarantine = quarantine
        self._library = library
        self._last_cancel_check = time.monotonic()
        self._flush_every = flush_every
        self._on_flush = on_flush
        self._unflushed: Counter[str] = Counter()
        self.parts: Counter[str] = Counter()
        self.index_job_ids: list[str] = []

    def archive_record(self, resource: str, record: JsonObject) -> None:
        self.archive.write(resource, record)
        if self._library is not None:
            self._library.write(resource, record)

    def publish_record(self, resource: str, record: JsonObject) -> None:
        RedisRecordStream(
            self._redis,
            RedisRecordStream.stream_name(self._job_id, resource),
            maxlen=self._redis_config.redis_stream_maxlen,
        ).publish(resource, record)
        self._unflushed[resource] += 1
        if self._unflushed[resource] >= self._flush_every:
            self.flush_resource(resource)

    def flush_resource(self, resource: str) -> None:
        """Queue an index job for records published since the last flush."""
        if self._on_flush is None or not self._unflushed[resource]:
            return
        self._unflushed[resource] = 0
        self.parts[resource] += 1
        job = self._on_flush(resource, self.parts[resource])
        if job is not None:
            self.index_job_ids.append(job)

    def flush_all(self) -> None:
        for resource in list(self._unflushed):
            self.flush_resource(resource)

    def update_progress(
        self, resource: str, stage: CoverageStage, values: dict[str, int | str | None]
    ) -> None:
        del stage
        self._store.update_coverage(self._job_id, resource, **values)
        now = time.monotonic()
        if now - self._last_cancel_check >= self.CANCEL_POLL_INTERVAL:
            self._last_cancel_check = now
            current = self._store.get(self._job_id)
            if current["status"] == JobStatus.CANCELLED.value:
                raise IngestCancelledError(self._job_id)

    def quarantine_validation_failure(
        self,
        resource: str,
        record: JsonObject,
        error: str,
        source_url: str | None,
    ) -> None:
        record_id = record.get("id")
        self._quarantine.write(
            resource,
            record,
            error=error,
            source_url=source_url,
            record_id=str(record_id) if record_id else None,
        )


class IngestJobRunner:
    # Resources denormalized into other documents are never indexed directly.
    NON_INDEXED_RESOURCES = frozenset({"summaries"})

    def __init__(
        self,
        store: JobStore,
        redis_client: Redis,
        submitter: JobSubmitter,
        redis_config: RedisConfig,
        congress_api: CongressApiConfig,
        bill_states: IndexedBillStateReader,
        library: RecordLibrary,
        rate_limiter: TokenBucket,
        partial_index_every: int,
        dispatcher: JobDispatcher,
        queues: QueueConfig,
    ) -> None:
        self._partial_index_every = partial_index_every
        self._dispatcher = dispatcher
        self._queues = queues
        self._store = store
        self._redis = redis_client
        self._submitter = submitter
        self._redis_config = redis_config
        self._congress_api = congress_api
        self._bill_states = bill_states
        self._library = library
        self._rate_limiter = rate_limiter

    @classmethod
    def should_queue_index_job(cls, resource: str) -> bool:
        return resource not in cls.NON_INDEXED_RESOURCES

    def run(self, job_id: str) -> JobResult:
        try:
            job = self._store.mark_running(
                job_id, max_active=self._queues.ingest_max_concurrent_jobs
            )
        except JobSlotsBusy:
            # Wait for a running job to finish rather than splitting the API budget.
            self._dispatcher.dispatch(
                JobKind.INGEST, job_id, countdown=self._queues.ingest_defer_seconds
            )
            return JobResult(job_id=job_id, deferred=True)
        if job is None:
            return SkippedClaim(self._store).result(job_id)
        payload = IngestPayload.model_validate(job["payload"])
        job_outdir = Path(payload.outdir) / job_id
        attempt = int(job["attempts"])
        session = IngestSession(
            job_id,
            self._store,
            self._redis,
            self._redis_config,
            JsonlRecordArchive(job_outdir, attempt),
            SQLiteQuarantineArchive(job_outdir),
            self._library_archive(payload),
            self._partial_index_every,
            lambda resource, part: self._flush_index(
                job_id, payload, job_outdir, resource, attempt, part
            ),
        )
        try:
            results = self._run_pipeline(payload, job_outdir, session)
            index_jobs = self._queue_index_jobs(
                job_id, payload, job_outdir, results, session
            )
        except IngestCancelledError:
            # Ledger already reflects the cancel; stop work without retrying.
            return JobResult(job_id=job_id, cancelled=True)
        except Exception:
            # Index what this attempt fetched so a retry skips it instead of redoing it.
            session.flush_all()
            raise
        self._store.mark_succeeded(job_id)
        return JobResult(job_id=job_id, index_jobs=index_jobs)

    def _library_archive(self, payload: IngestPayload) -> LatestRecordArchive | None:
        if not payload.retain_records:
            return None
        label = (
            f"congress-{payload.congress}" if payload.congress is not None else "all"
        )
        return self._library.archive(label)

    def _item_filter(self, payload: IngestPayload) -> StaleBillFilter | None:
        if not payload.refresh_stale or payload.congress is None:
            return None
        return StaleBillFilter(self._bill_states.read(payload.congress))

    def _run_pipeline(
        self, payload: IngestPayload, job_outdir: Path, session: IngestSession
    ) -> list[ResourceResult]:
        config = PipelineConfig(
            outdir=job_outdir,
            from_date=payload.from_date,
            to_date=payload.to_date,
            congress=payload.congress,
            fetch_items=payload.fetch_items,
            force_item_fetch=payload.force_item_fetch,
            item_resources=frozenset(payload.item_resources or ()),
            max_pages=payload.max_pages,
            max_items=payload.max_items,
            list_page_size=payload.list_page_size,
            max_skipped_list_pages=payload.max_skipped_list_pages,
            concurrency=payload.concurrency,
            rate_limiter=self._rate_limiter,
            api_key=payload.api_key,
            skip_errors=False,
            record_sink=session.publish_record,
            record_archive_sink=session.archive_record,
            validation_failure_sink=session.quarantine_validation_failure,
            progress_sink=session.update_progress,
            item_filter=self._item_filter(payload),
        )
        selected = [Resource(name) for name in payload.resources or ()]
        pipeline = Pipeline(config)
        results = pipeline.run(selected) if selected else pipeline.run_all()
        failed = [result for result in results if not result.success]
        if failed:
            raise RuntimeError(
                "Ingest failed for: "
                + ", ".join(result.resource.value for result in failed)
            )
        return results

    def _queue_index_jobs(
        self,
        job_id: str,
        payload: IngestPayload,
        job_outdir: Path,
        results: list[ResourceResult],
        session: IngestSession,
    ) -> list[str]:
        if not payload.index:
            return []
        for result in results:
            resource = result.resource.value
            if not result.published_count or not self.should_queue_index_job(resource):
                continue
            if session.parts[resource]:
                session.flush_resource(resource)
            else:
                session.index_job_ids.append(
                    self._submit_index(
                        job_id, payload, job_outdir, resource, result.published_count
                    )
                )
        return session.index_job_ids

    def _flush_index(
        self,
        job_id: str,
        payload: IngestPayload,
        job_outdir: Path,
        resource: str,
        attempt: int,
        part: int,
    ) -> str | None:
        if not payload.index or not self.should_queue_index_job(resource):
            return None
        return self._submit_index(
            job_id, payload, job_outdir, resource, None, attempt=attempt, part=part
        )

    def _submit_index(
        self,
        job_id: str,
        payload: IngestPayload,
        job_outdir: Path,
        resource: str,
        expected_count: int | None,
        *,
        attempt: int | None = None,
        part: int | None = None,
    ) -> str:
        index_payload = IndexPayload(
            stream=RedisRecordStream.stream_name(job_id, resource),
            resource=resource,
            batch_size=payload.index_batch_size,
            preserve_raw=payload.preserve_raw,
            consumer_group=self._redis_config.redis_consumer_group,
            expected_count=expected_count,
            archive_root=str(job_outdir),
        )
        if attempt is not None:
            index_payload.source_attempt = attempt
        if part is not None:
            index_payload.part = part
        return self._submitter.submit(JobKind.INDEX, index_payload.to_json())["id"]

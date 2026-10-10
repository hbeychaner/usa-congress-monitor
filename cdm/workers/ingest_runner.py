"""Runs one durable ingest job: pipeline -> Redis streams -> index jobs."""

from __future__ import annotations

import time
from pathlib import Path

from redis import Redis

from cdm.config.app_config import CongressApiConfig, RedisConfig
from cdm.ingest.archive import JsonlRecordArchive, SQLiteQuarantineArchive
from cdm.ingest.pipeline import Pipeline, PipelineConfig, ResourceResult
from cdm.ingest.redis_stream import RedisRecordStream
from cdm.ingest.runner import IngestCancelledError, Resource
from cdm.jobs.payloads import IndexPayload, IngestPayload
from cdm.jobs.store import CoverageStage, JobKind, JobStatus, JobStore
from cdm.utils.json_types import JsonObject
from cdm.utils.rate_limiter import TokenBucket
from cdm.workers.dispatch import JobSubmitter
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
    ) -> None:
        self._job_id = job_id
        self._store = store
        self._redis = redis_client
        self._redis_config = redis_config
        self.archive = archive
        self._quarantine = quarantine
        self._last_cancel_check = time.monotonic()

    def publish_record(self, resource: str, record: JsonObject) -> None:
        RedisRecordStream(
            self._redis,
            RedisRecordStream.stream_name(self._job_id, resource),
            maxlen=self._redis_config.redis_stream_maxlen,
        ).publish(resource, record)

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
    ) -> None:
        self._store = store
        self._redis = redis_client
        self._submitter = submitter
        self._redis_config = redis_config
        self._congress_api = congress_api

    @classmethod
    def should_queue_index_job(cls, resource: str) -> bool:
        return resource not in cls.NON_INDEXED_RESOURCES

    def run(self, job_id: str) -> JobResult:
        job = self._store.mark_running(job_id)
        if job is None:
            return SkippedClaim(self._store).result(job_id)
        payload = IngestPayload.model_validate(job["payload"])
        job_outdir = Path(payload.outdir) / job_id
        session = IngestSession(
            job_id,
            self._store,
            self._redis,
            self._redis_config,
            JsonlRecordArchive(job_outdir, int(job["attempts"])),
            SQLiteQuarantineArchive(job_outdir),
        )
        try:
            results = self._run_pipeline(payload, job_outdir, session)
            index_jobs = self._queue_index_jobs(job_id, payload, job_outdir, results)
        except IngestCancelledError:
            # Ledger already reflects the cancel; stop work without retrying.
            return JobResult(job_id=job_id, cancelled=True)
        self._store.mark_succeeded(job_id)
        return JobResult(job_id=job_id, index_jobs=index_jobs)

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
            rate_limiter=TokenBucket(
                rate_per_hour=self._congress_api.ingest_rate_limit_per_hour
            ),
            api_key=payload.api_key,
            skip_errors=False,
            record_sink=session.publish_record,
            record_archive_sink=session.archive.write,
            validation_failure_sink=session.quarantine_validation_failure,
            progress_sink=session.update_progress,
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
    ) -> list[str]:
        if not payload.index:
            return []
        index_jobs: list[str] = []
        for result in results:
            resource = result.resource.value
            if not result.published_count or not self.should_queue_index_job(resource):
                continue
            index_payload = IndexPayload(
                stream=RedisRecordStream.stream_name(job_id, resource),
                resource=resource,
                batch_size=payload.index_batch_size,
                preserve_raw=payload.preserve_raw,
                consumer_group=self._redis_config.redis_consumer_group,
                expected_count=result.published_count,
                archive_root=str(job_outdir),
            )
            job = self._submitter.submit(JobKind.INDEX, index_payload.to_json())
            index_jobs.append(job["id"])
        return index_jobs

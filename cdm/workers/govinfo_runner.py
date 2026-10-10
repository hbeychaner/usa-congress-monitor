"""Runners for GovInfo package, batch, and reconciliation jobs."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Protocol

import requests
from elasticsearch import Elasticsearch
from kombu.exceptions import OperationalError
from redis import Redis

from cdm.config.app_config import RedisConfig
from cdm.ingest.archive import JsonlRecordArchive
from cdm.ingest.govinfo import (
    GovInfoBillsParser,
    GovInfoBillStatusParser,
    GovInfoBillSummaryParser,
    GovInfoDownloader,
    GovInfoManifestStore,
    GovInfoPackage,
)
from cdm.ingest.reconciliation import replay_govinfo_archives
from cdm.ingest.redis_stream import RedisRecordStream
from cdm.jobs.payloads import (
    GovInfoBatchPayload,
    GovInfoPackagePayload,
    IndexPayload,
    ReconcilePayload,
)
from cdm.jobs.store import JobKind, JobStore
from cdm.utils.json_types import JsonObject
from cdm.utils.rate_limiter import TokenBucket
from cdm.workers.dispatch import JobDispatcher, JobSubmitter
from cdm.workers.results import JobResult, SkippedClaim


class GovInfoCollection(StrEnum):
    BILLSTATUS = "BILLSTATUS"
    BILLSUM = "BILLSUM"
    BILLS = "BILLS"


class GovInfoRecordParser(Protocol):
    def parse(self, content: bytes, package: GovInfoPackage) -> JsonObject: ...


class GovInfoCollectionSpec:
    """How one GovInfo collection is parsed and which resource it feeds."""

    def __init__(
        self, parser: GovInfoRecordParser, resource: str, parser_version: str
    ) -> None:
        self.parser = parser
        self.resource = resource
        self.parser_version = parser_version


class GovInfoPackageRunner:
    """Download, normalize, archive, and queue one GovInfo package."""

    def __init__(
        self,
        store: JobStore,
        redis_client: Redis,
        submitter: JobSubmitter,
        dispatcher: JobDispatcher,
        redis_config: RedisConfig,
        session: requests.Session,
        rate_limiter: TokenBucket,
    ) -> None:
        self._store = store
        self._redis = redis_client
        self._submitter = submitter
        self._dispatcher = dispatcher
        self._redis_config = redis_config
        self._session = session
        self._rate_limiter = rate_limiter
        self._collections = {
            GovInfoCollection.BILLSTATUS: GovInfoCollectionSpec(
                GovInfoBillStatusParser(), "bill", "govinfo-billstatus-v1"
            ),
            GovInfoCollection.BILLSUM: GovInfoCollectionSpec(
                GovInfoBillSummaryParser(), "bill", "govinfo-billsum-v1"
            ),
            GovInfoCollection.BILLS: GovInfoCollectionSpec(
                GovInfoBillsParser(), "bill_text", "govinfo-bills-v1"
            ),
        }

    def run(self, job_id: str) -> JobResult:
        job = self._store.mark_running(job_id, update_windows=False)
        if job is None:
            return SkippedClaim(self._store).result(job_id)
        payload = GovInfoPackagePayload.model_validate(job["payload"])
        package = GovInfoPackage(
            package_id=payload.package_id,
            collection=payload.collection,
            congress=payload.congress,
            measure_type=payload.measure_type,
            url=payload.url,
            session=payload.session,
            version_code=payload.version_code,
        )
        try:
            spec = self._collections[GovInfoCollection(package.collection)]
        except ValueError:
            raise ValueError(
                f"Unsupported GovInfo collection: {package.collection}"
            ) from None
        outdir = Path(payload.outdir) / job_id
        manifest = GovInfoManifestStore(outdir / "govinfo.sqlite3")
        artifact = GovInfoDownloader(
            outdir,
            manifest_store=manifest,
            session=self._session,
            rate_limiter=self._rate_limiter,
        ).download(package)
        record = spec.parser.parse(artifact.read_bytes(), package)
        manifest.upsert(
            package,
            status="parsed",
            path=str(artifact),
            byte_count=artifact.stat().st_size,
            sha256=GovInfoDownloader._sha256(artifact),
            parser_version=spec.parser_version,
            fetched_at=GovInfoDownloader._now(),
        )
        JsonlRecordArchive(outdir, int(job["attempts"])).write(
            spec.resource, record, record_id=package.package_id
        )
        stream_name = RedisRecordStream.stream_name(job_id, spec.resource)
        RedisRecordStream(
            self._redis, stream_name, maxlen=self._redis_config.redis_stream_maxlen
        ).publish(spec.resource, record)
        index_payload = IndexPayload(
            stream=stream_name,
            resource=spec.resource,
            batch_size=1,
            preserve_raw=True,
            consumer_group=self._redis_config.redis_consumer_group,
            expected_count=1,
            archive_root=str(outdir),
            target_index=payload.target_index,
            replace=payload.replace,
            # A re-parse must not collide with the previous run's succeeded index job.
            source_attempt=int(job["attempts"]),
        )
        index_job = self._submitter.submit(
            JobKind.INDEX, index_payload.to_json(), dispatch=False
        )
        self._store.mark_succeeded(job_id)
        try:
            self._dispatcher.dispatch(JobKind.INDEX, index_job["id"])
        except (OperationalError, ConnectionError):
            # The durable index row remains queued for periodic recovery.
            pass
        return JobResult(
            job_id=job_id, index_jobs=[index_job["id"]], resource=spec.resource
        )


class GovInfoBatchRunner:
    """Fan out a durable batch into independently retryable package tasks."""

    def __init__(self, store: JobStore, dispatcher: JobDispatcher) -> None:
        self._store = store
        self._dispatcher = dispatcher

    def run(self, batch_id: str) -> JobResult:
        batch = self._store.mark_running(batch_id)
        if batch is None:
            return SkippedClaim(self._store).result(batch_id)
        payload = GovInfoBatchPayload.model_validate(batch["payload"])
        for package_job_id in payload.job_ids:
            self._dispatcher.dispatch(JobKind.GOVINFO_BULK, package_job_id)
        self._store.mark_succeeded(batch_id)
        return JobResult(job_id=batch_id, packages_dispatched=payload.job_ids)


class ReconciliationRunner:
    """Replay archived GovInfo records into a validated staging index."""

    def __init__(self, store: JobStore, client: Elasticsearch) -> None:
        self._store = store
        self._client = client

    def run(self, job_id: str) -> JobResult:
        job = self._store.mark_running(job_id)
        if job is None:
            return SkippedClaim(self._store).result(job_id)
        payload = ReconcilePayload.model_validate(job["payload"])
        result = replay_govinfo_archives(
            Path(payload.archive_root),
            self._client,
            target_index=payload.target_index,
            report_path=Path(payload.report_path),
            preserve_raw=payload.preserve_raw,
        )
        self._store.mark_succeeded(job_id)
        return JobResult(job_id=job_id, **result)

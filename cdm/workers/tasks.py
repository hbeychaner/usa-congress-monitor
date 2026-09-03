"""Thin Celery wrappers around durable ingest and indexing services."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, NoReturn

import requests
from celery.exceptions import MaxRetriesExceededError
from redis import Redis

from cdm.ingest.archive import JsonlRecordArchive
from cdm.ingest.govinfo import (
    GovInfoBillsParser,
    GovInfoBillStatusParser,
    GovInfoBillSummaryParser,
    GovInfoDownloader,
    GovInfoManifestStore,
    GovInfoPackage,
)
from cdm.ingest.pipeline import Pipeline, PipelineConfig
from cdm.ingest.rate_limiter import TokenBucket
from cdm.ingest.reconciliation import replay_govinfo_archives
from cdm.ingest.redis_stream import RedisRecordStream
from cdm.ingest.resource_config import congress_scoped, date_windowed
from cdm.jobs.store import CoverageStage, JobKind, JobStatus, JobStore
from cdm.store.client import get_opensearch_client
from cdm.store.index_manager import IndexManager
from cdm.store.opensearch import resource_target
from cdm.store.redis_indexing import RedisIndexingRunner
from cdm.workers.celery_app import celery_app
from settings import (
    CELERY_INDEX_QUEUE,
    CELERY_INGEST_QUEUE,
    CELERY_RETRY_BACKOFF_MAX,
    CELERY_RETRY_MAX,
    CELERY_RETRY_MAX_TRANSIENT,
    ES_LOCAL_API_KEY,
    ES_LOCAL_URL,
    JOB_DB_PATH,
    REDIS_CONSUMER_GROUP,
    REDIS_STREAM_MAXLEN,
    REDIS_URL,
)


def _store() -> JobStore:
    return JobStore(JOB_DB_PATH)


def _redis() -> Redis:
    return Redis.from_url(REDIS_URL)


_GOVINFO_SESSION: requests.Session | None = None


def _govinfo_session() -> requests.Session:
    global _GOVINFO_SESSION
    if _GOVINFO_SESSION is None:
        _GOVINFO_SESSION = requests.Session()
    return _GOVINFO_SESSION


def _job_id(kind: str, payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode()).hexdigest()[:24]
    return f"{kind}:{digest}"


def submit_job(
    kind: str,
    payload: dict[str, Any],
    *,
    store: JobStore | None = None,
    dispatch_existing: bool = True,
    dispatch: bool = True,
) -> dict:
    job_id = _job_id(kind, payload)
    job_store = store or _store()
    existing = None
    if not dispatch_existing:
        try:
            existing = job_store.get(job_id)
        except KeyError:
            pass
    job = job_store.create(kind, job_id, payload)
    should_dispatch = dispatch and (
        existing is None or job["status"] == JobStatus.FAILED
    )
    if should_dispatch and job["status"] in {JobStatus.QUEUED, JobStatus.FAILED}:
        if kind == JobKind.INGEST:
            celery_app.send_task(
                "cdm.workers.tasks.run_ingest_job",
                args=[job_id],
                queue=CELERY_INGEST_QUEUE,
            )
        elif kind == JobKind.INDEX:
            celery_app.send_task(
                "cdm.workers.tasks.run_index_job",
                args=[job_id],
                queue=CELERY_INDEX_QUEUE,
            )
        elif kind == JobKind.GOVINFO_BULK:
            celery_app.send_task(
                "cdm.workers.tasks.run_govinfo_bulk_job",
                args=[job_id],
                queue=CELERY_INGEST_QUEUE,
            )
        elif kind == JobKind.GOVINFO_BULK_BATCH:
            celery_app.send_task(
                "cdm.workers.tasks.run_govinfo_bulk_batch",
                args=[job_id],
                queue=CELERY_INGEST_QUEUE,
            )
        elif kind == JobKind.RECONCILE:
            celery_app.send_task(
                "cdm.workers.tasks.run_reconciliation_job",
                args=[job_id],
                queue=CELERY_INDEX_QUEUE,
            )
    return job


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, requests.HTTPError):
        response = exc.response
        return response is not None and (
            response.status_code == 429 or response.status_code >= 500
        )
    return isinstance(exc, (requests.ConnectionError, requests.Timeout))


def _is_retryable_error(error: str | None) -> bool:
    if not error:
        return False
    return error.startswith((
        "server error: 5",
        "server error: 429",
        "HTTP 5",
        "HTTP 429",
    )) or any(
        marker in error.lower()
        for marker in ("connectionerror", "connection aborted", "timed out")
    )


def _retry(task: Any, job_id: str, exc: Exception) -> NoReturn:
    store = _store()
    if not _is_transient(exc):
        store.mark_failed(job_id, str(exc))
        raise exc
    store.mark_retrying(job_id, str(exc))
    max_retries = CELERY_RETRY_MAX_TRANSIENT if _is_transient(exc) else CELERY_RETRY_MAX
    try:
        raise task.retry(
            exc=exc,
            countdown=min(
                CELERY_RETRY_BACKOFF_MAX,
                2 ** min(task.request.retries, 10),
            ),
            max_retries=max_retries,
        )
    except MaxRetriesExceededError:
        store.mark_failed(job_id, str(exc))
        raise


@celery_app.task(bind=True, name="cdm.workers.tasks.run_ingest_job")
def run_ingest_job(self, job_id: str) -> dict:
    store = _store()
    job = store.mark_running(job_id)
    if job["status"] != JobStatus.RUNNING:
        return {"job_id": job_id, "skipped": True, "status": job["status"]}
    payload = job["payload"]
    try:
        redis_client = _redis()
        job_outdir = Path(payload["outdir"]) / job_id
        archive = JsonlRecordArchive(job_outdir, int(job["attempts"]))

        def publish_record(resource: str, record: dict) -> None:
            stream = RedisRecordStream(
                redis_client,
                RedisRecordStream.stream_name(job_id, resource),
                maxlen=REDIS_STREAM_MAXLEN,
            )
            stream.publish(resource, record)

        def update_progress(resource: str, stage: CoverageStage, values: dict) -> None:
            del stage
            store.update_coverage(job_id, resource, **values)

        resources = payload.get("resources")
        config = PipelineConfig(
            outdir=job_outdir,
            from_date=payload.get("from_date"),
            to_date=payload.get("to_date"),
            congress=payload.get("congress"),
            fetch_items=bool(payload.get("fetch_items", False)),
            force_item_fetch=bool(payload.get("force_item_fetch", False)),
            max_pages=payload.get("max_pages"),
            max_items=payload.get("max_items"),
            list_page_size=int(payload.get("list_page_size", 250)),
            concurrency=int(payload.get("concurrency", 1)),
            rate_limiter=TokenBucket(rate_per_hour=4800),
            api_key=payload.get("api_key"),
            skip_errors=False,
            record_sink=publish_record,
            record_archive_sink=archive.write,
            progress_sink=update_progress,
        )
        selected = None
        if resources:
            from cdm.ingest.runner import Resource

            selected = [Resource(resource) for resource in resources]
        results = (
            Pipeline(config).run(selected) if selected else Pipeline(config).run_all()
        )
        failed = [result for result in results if not result.success]
        if failed:
            raise RuntimeError(
                "Ingest failed for: "
                + ", ".join(result.resource.value for result in failed)
            )

        index_jobs = []
        if payload.get("index", True):
            for result in results:
                if result.published_count:
                    index_payload = {
                        "stream": RedisRecordStream.stream_name(
                            job_id, result.resource.value
                        ),
                        "resource": result.resource.value,
                        "batch_size": int(payload.get("index_batch_size", 500)),
                        "preserve_raw": bool(payload.get("preserve_raw", False)),
                        "consumer_group": REDIS_CONSUMER_GROUP,
                        "expected_count": result.published_count,
                        "archive_root": str(job_outdir),
                    }
                    index_jobs.append(submit_job("index", index_payload)["id"])
        store.mark_succeeded(job_id)
        return {"job_id": job_id, "index_jobs": index_jobs}
    except Exception as exc:  # noqa: BLE001 - Celery must retry all ordinary task failures.
        _retry(self, job_id, exc)


def _process_govinfo_bulk_job(job_id: str) -> dict:
    """Download, normalize, archive, and queue one GovInfo package."""
    store = _store()
    job = store.claim_running(job_id)
    if job is None:
        existing = store.get(job_id)
        return {"job_id": job_id, "skipped": True, "status": existing["status"]}
    payload = job["payload"]
    package = GovInfoPackage(
        package_id=payload["package_id"],
        collection=payload["collection"],
        congress=int(payload["congress"]),
        measure_type=payload["measure_type"],
        url=payload["url"],
        session=payload.get("session"),
        version_code=payload.get("version_code"),
    )
    outdir = Path(payload["outdir"]) / job_id
    manifest = GovInfoManifestStore(outdir / "govinfo.sqlite3")
    downloader = GovInfoDownloader(
        outdir,
        manifest_store=manifest,
        session=_govinfo_session(),
    )
    artifact = downloader.download(package)
    if package.collection == "BILLSTATUS":
        record = GovInfoBillStatusParser().parse(artifact.read_bytes(), package)
        resource = "bill"
        parser_version = "govinfo-billstatus-v1"
    elif package.collection == "BILLSUM":
        record = GovInfoBillSummaryParser().parse(artifact.read_bytes(), package)
        resource = "bill"
        parser_version = "govinfo-billsum-v1"
    elif package.collection == "BILLS":
        record = GovInfoBillsParser().parse(artifact.read_bytes(), package)
        resource = "bill_text"
        parser_version = "govinfo-bills-v1"
    else:
        raise ValueError(f"Unsupported GovInfo collection: {package.collection}")
    manifest.upsert(
        package,
        status="parsed",
        path=str(artifact),
        byte_count=artifact.stat().st_size,
        sha256=GovInfoDownloader._sha256(artifact),
        parser_version=parser_version,
        fetched_at=GovInfoDownloader._now(),
    )
    archive = JsonlRecordArchive(outdir, int(job["attempts"]))
    archive.write(resource, record, record_id=package.package_id)
    stream_name = RedisRecordStream.stream_name(job_id, resource)
    RedisRecordStream(_redis(), stream_name, maxlen=REDIS_STREAM_MAXLEN).publish(
        resource, record
    )
    index_job = submit_job(
        "index",
        {
            "stream": stream_name,
            "resource": resource,
            "batch_size": 1,
            "preserve_raw": True,
            "consumer_group": REDIS_CONSUMER_GROUP,
            "expected_count": 1,
            "archive_root": str(outdir),
            "target_index": payload.get("target_index"),
            "replace": bool(payload.get("replace", False)),
        },
    )
    store.mark_succeeded(job_id)
    return {"job_id": job_id, "index_jobs": [index_job["id"]], "resource": resource}


@celery_app.task(bind=True, name="cdm.workers.tasks.run_govinfo_bulk_job")
def run_govinfo_bulk_job(self, job_id: str) -> dict:
    """Run one durable GovInfo package job."""
    try:
        return _process_govinfo_bulk_job(job_id)
    except Exception as exc:  # noqa: BLE001 - Celery must retry ordinary failures.
        _retry(self, job_id, exc)


@celery_app.task(bind=True, name="cdm.workers.tasks.run_govinfo_bulk_batch")
def run_govinfo_bulk_batch(self, batch_id: str) -> dict:
    """Fan out a durable batch into independently retryable package tasks."""
    store = _store()
    batch = store.mark_running(batch_id)
    if batch["status"] != JobStatus.RUNNING:
        return {"job_id": batch_id, "skipped": True, "status": batch["status"]}

    dispatched = []
    for package_job_id in batch["payload"]["job_ids"]:
        celery_app.send_task(
            "cdm.workers.tasks.run_govinfo_bulk_job",
            args=[package_job_id],
            queue=CELERY_INGEST_QUEUE,
        )
        dispatched.append(package_job_id)
    store.mark_succeeded(batch_id)
    return {"job_id": batch_id, "packages_dispatched": dispatched}


@celery_app.task(bind=True, name="cdm.workers.tasks.run_index_job")
def run_index_job(self, job_id: str) -> dict:
    store = _store()
    job = store.mark_running(job_id)
    if job["status"] != JobStatus.RUNNING:
        return {"job_id": job_id, "skipped": True, "status": job["status"]}
    payload = job["payload"]
    try:
        client = get_opensearch_client(url=ES_LOCAL_URL, api_key=ES_LOCAL_API_KEY)
        target, _ = resource_target(payload["resource"])
        target_index = payload.get("target_index")
        if target_index:
            if not client.indices.exists(index=target_index):
                raise RuntimeError(
                    f"Configured staging index does not exist: {target_index}"
                )
        else:
            IndexManager(client).create(target, exists_ok=True)
        result = RedisIndexingRunner(
            redis_client=_redis(),
            opensearch_client=client,
            stream=payload["stream"],
            resource=payload["resource"],
            batch_size=int(payload.get("batch_size", 500)),
            consumer_group=payload.get("consumer_group", REDIS_CONSUMER_GROUP),
            preserve_raw=bool(payload.get("preserve_raw", False)),
            target_index=target_index,
            replace=bool(payload.get("replace", False)),
        ).run()
        expected_count = payload.get("expected_count")
        if result["pending"] != 0:
            raise RuntimeError(
                f"Redis stream still has {result['pending']} pending entries: "
                f"{payload['stream']}"
            )
        if expected_count is not None and result["indexed"] < int(expected_count):
            raise RuntimeError(
                f"Indexed {result['indexed']} records, expected at least {expected_count}: "
                f"{payload['stream']}"
            )
        store.mark_succeeded(job_id)
        return result
    except Exception as exc:  # noqa: BLE001 - Celery must retry all ordinary task failures.
        _retry(self, job_id, exc)


@celery_app.task(bind=True, name="cdm.workers.tasks.run_reconciliation_job")
def run_reconciliation_job(self, job_id: str) -> dict:
    """Replay archived GovInfo records into a validated staging index."""
    store = _store()
    job = store.mark_running(job_id)
    if job["status"] != JobStatus.RUNNING:
        return {"job_id": job_id, "skipped": True, "status": job["status"]}
    payload = job["payload"]
    try:
        client = get_opensearch_client(url=ES_LOCAL_URL, api_key=ES_LOCAL_API_KEY)
        result = replay_govinfo_archives(
            Path(payload["archive_root"]),
            client,
            target_index=payload["target_index"],
            report_path=Path(payload["report_path"]),
            preserve_raw=bool(payload.get("preserve_raw", True)),
        )
        store.mark_succeeded(job_id)
        return {"job_id": job_id, **result}
    except Exception as exc:  # noqa: BLE001 - Celery must retry ordinary failures.
        _retry(self, job_id, exc)


@celery_app.task(name="cdm.workers.tasks.schedule_daily_ingest")
def schedule_daily_ingest() -> dict:
    payload = daily_ingest_payload(datetime.now(UTC).date())
    return submit_job("ingest", payload)


def coverage_gap_payloads(now: datetime | None = None) -> list[dict[str, Any]]:
    """Build jobs for date-windowed resources stale by more than 24 hours."""
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    store = _store()
    payloads = []
    for config in date_windowed():
        resource = config.resource.value
        completed = [
            row
            for row in store.coverage(resource)
            if row["status"] == JobStatus.SUCCEEDED.value and row["window_end"]
        ]
        if not completed:
            continue
        latest = max(
            datetime.fromisoformat(str(row["window_end"])) for row in completed
        )
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=UTC)
        if current - latest <= timedelta(hours=24):
            continue
        payloads.append({
            "outdir": "data/daily",
            "resources": [resource],
            "from_date": latest
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "to_date": current
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "fetch_items": config.fetch_items_default,
            "index": True,
            "concurrency": 4,
            "index_batch_size": 500,
            "mode": "coverage_gap",
        })
    return payloads


@celery_app.task(name="cdm.workers.tasks.schedule_coverage_gaps")
def schedule_coverage_gaps() -> dict:
    """Queue idempotent jobs for date-windowed coverage gaps over 24 hours."""
    queued = []
    for payload in coverage_gap_payloads():
        queued.append(submit_job(JobKind.INGEST.value, payload)["id"])
    return {"queued": queued, "count": len(queued)}


def daily_ingest_payload(today) -> dict:
    """Build the bounded recurring-ingest payload for a UTC calendar day.

    Date-capable resources are queried with a small overlap so late API
    updates are discovered. Congress-scoped resources are limited to the
    current Congress. Static resources are excluded because their endpoints
    provide no server-side incremental filter.
    """
    start = today - timedelta(days=2)
    from_date = start.isoformat() + "T00:00:00Z"
    to_date = today.isoformat() + "T23:59:59Z"
    resources = sorted({
        config.resource.value for config in (*date_windowed(), *congress_scoped())
    })
    payload = {
        "outdir": "data/daily",
        "resources": resources,
        "from_date": from_date,
        "to_date": to_date,
        "congress": (today.year - 1787) // 2,
        "fetch_items": True,
        "index": True,
        "concurrency": 4,
        "index_batch_size": 500,
        "schedule_date": today.isoformat(),
        "mode": "daily_incremental",
    }
    return payload


@celery_app.task(name="cdm.workers.tasks.recover_failed_ingest_jobs")
def recover_failed_ingest_jobs() -> dict:
    """Requeue failed or stale jobs stranded by a worker restart."""
    redis_client = _redis()
    recovery_lock = redis_client.lock(
        "congress:workers:recover_failed_ingest_jobs",
        timeout=3600,
        blocking=False,
    )
    if not recovery_lock.acquire():
        return {"recovered": [], "skipped": "already_running"}

    try:
        store = _store()
        recovered = []
        cutoff = datetime.now(UTC) - timedelta(minutes=15)
        candidates = [
            *store.failed(),
            *[
                job
                for job in store.jobs()
                if job["status"] in {JobStatus.RUNNING, JobStatus.RETRYING}
                and datetime.fromisoformat(job["updated_at"]) < cutoff
            ],
        ]
        batched_package_ids = {
            package_id
            for batch in store.jobs(JobKind.GOVINFO_BULK_BATCH.value)
            if batch["status"]
            in {JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.RETRYING}
            for package_id in batch["payload"].get("job_ids", [])
        }
        seen = set()
        for job in candidates:
            if job["id"] in seen:
                continue
            seen.add(job["id"])
            if job["kind"] == JobKind.GOVINFO_BULK and job["id"] in batched_package_ids:
                continue
            if job["status"] == JobStatus.FAILED and not _is_retryable_error(
                job["last_error"]
            ):
                continue
            requeued = (
                store.requeue(job["id"]) if job["status"] != JobStatus.QUEUED else job
            )
            if job["kind"] == JobKind.INGEST:
                task_name = "cdm.workers.tasks.run_ingest_job"
            elif job["kind"] == JobKind.INDEX:
                task_name = "cdm.workers.tasks.run_index_job"
            elif job["kind"] == JobKind.GOVINFO_BULK_BATCH:
                task_name = "cdm.workers.tasks.run_govinfo_bulk_batch"
            else:
                task_name = "cdm.workers.tasks.run_govinfo_bulk_job"
            queue = (
                CELERY_INGEST_QUEUE
                if job["kind"]
                in {
                    JobKind.INGEST,
                    JobKind.GOVINFO_BULK,
                    JobKind.GOVINFO_BULK_BATCH,
                }
                else CELERY_INDEX_QUEUE
            )
            celery_app.send_task(
                task_name,
                args=[requeued["id"]],
                queue=queue,
            )
            recovered.append(requeued["id"])
        return {"recovered": recovered}
    finally:
        recovery_lock.release()

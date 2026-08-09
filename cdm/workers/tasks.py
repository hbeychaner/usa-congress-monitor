"""Thin Celery wrappers around durable ingest and indexing services."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, NoReturn

from redis import Redis

from cdm.ingest.archive import JsonlRecordArchive
from cdm.ingest.pipeline import Pipeline, PipelineConfig
from cdm.ingest.redis_stream import RedisRecordStream
from cdm.jobs.store import JobStore
from cdm.store.client import get_opensearch_client
from cdm.store.index_manager import IndexManager
from cdm.store.opensearch import resource_target
from cdm.store.redis_indexing import RedisIndexingRunner
from cdm.workers.celery_app import celery_app
from settings import (
    CELERY_RETRY_BACKOFF_MAX,
    CELERY_RETRY_MAX,
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


def _job_id(kind: str, payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode()).hexdigest()[:24]
    return f"{kind}:{digest}"


def submit_job(kind: str, payload: dict[str, Any]) -> dict:
    job_id = _job_id(kind, payload)
    job = _store().create(kind, job_id, payload)
    if job["status"] in {"queued", "failed"}:
        if kind == "ingest":
            celery_app.send_task("cdm.workers.tasks.run_ingest_job", args=[job_id])
        elif kind == "index":
            celery_app.send_task("cdm.workers.tasks.run_index_job", args=[job_id])
    return job


def _retry(task: Any, job_id: str, exc: Exception) -> NoReturn:
    _store().mark_failed(job_id, str(exc))
    raise task.retry(
        exc=exc,
        countdown=min(
            CELERY_RETRY_BACKOFF_MAX,
            2 ** min(task.request.retries, 10),
        ),
        max_retries=CELERY_RETRY_MAX,
    )


@celery_app.task(bind=True, name="cdm.workers.tasks.run_ingest_job")
def run_ingest_job(self, job_id: str) -> dict:
    store = _store()
    job = store.mark_running(job_id)
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
            concurrency=int(payload.get("concurrency", 1)),
            api_key=payload.get("api_key"),
            skip_errors=False,
            record_sink=publish_record,
            record_archive_sink=archive.write,
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
                if result.item_count:
                    index_payload = {
                        "stream": RedisRecordStream.stream_name(
                            job_id, result.resource.value
                        ),
                        "resource": result.resource.value,
                        "batch_size": int(payload.get("index_batch_size", 500)),
                        "preserve_raw": bool(payload.get("preserve_raw", False)),
                        "consumer_group": REDIS_CONSUMER_GROUP,
                    }
                    index_jobs.append(submit_job("index", index_payload)["id"])
        store.mark_succeeded(job_id)
        return {"job_id": job_id, "index_jobs": index_jobs}
    except Exception as exc:  # noqa: BLE001 - Celery must retry all ordinary task failures.
        _retry(self, job_id, exc)


@celery_app.task(bind=True, name="cdm.workers.tasks.run_index_job")
def run_index_job(self, job_id: str) -> dict:
    store = _store()
    job = store.mark_running(job_id)
    payload = job["payload"]
    try:
        client = get_opensearch_client(url=ES_LOCAL_URL, api_key=ES_LOCAL_API_KEY)
        target, _ = resource_target(payload["resource"])
        IndexManager(client).create(target, exists_ok=True)
        result = RedisIndexingRunner(
            redis_client=_redis(),
            opensearch_client=client,
            stream=payload["stream"],
            resource=payload["resource"],
            batch_size=int(payload.get("batch_size", 500)),
            consumer_group=payload.get("consumer_group", REDIS_CONSUMER_GROUP),
            preserve_raw=bool(payload.get("preserve_raw", False)),
        ).run()
        store.mark_succeeded(job_id)
        return result
    except Exception as exc:  # noqa: BLE001 - Celery must retry all ordinary task failures.
        _retry(self, job_id, exc)


@celery_app.task(name="cdm.workers.tasks.schedule_daily_ingest")
def schedule_daily_ingest() -> dict:
    today = datetime.now(UTC).date()
    start = today - timedelta(days=2)
    payload = {
        "outdir": "data/daily",
        "from_date": start.isoformat(),
        "to_date": today.isoformat(),
        "fetch_items": True,
        "index": True,
        "concurrency": 4,
        "index_batch_size": 500,
        "schedule_date": today.isoformat(),
    }
    return submit_job("ingest", payload)

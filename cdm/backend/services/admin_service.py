from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from elastic_transport import TransportError
from sqlalchemy import Column, MetaData, String, Table, create_engine, func, select

from cdm.contracts.api import (
    AdminIngestSnapshot,
    GovInfoCoverage,
    IngestProgressJob,
    IngestProgressResponse,
    JobStatusCounts,
    StagingStatus,
)
from cdm.store.client import get_opensearch_client
from settings import (
    CONGRESS_API_KEY,
    CONGRESS_API_URL,
    ES_LOCAL_API_KEY,
    ES_LOCAL_URL,
    JOB_DB_PATH,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GOVINFO_REPORT = (
    _REPO_ROOT / "data" / "full_history" / "govinfo" / "coverage-report-118.json"
)
_STAGING_INDEX = "congress-legislation-v118"
_JOBS_ENGINE = create_engine(f"sqlite:///{JOB_DB_PATH}")
_JOBS_TABLE = Table(
    "jobs",
    MetaData(),
    Column("id", String),
    Column("status", String),
)


@dataclass
class _ActiveJob:
    job_id: str
    status: str
    resource: str
    outdir: Path
    from_date: str | None
    to_date: str | None
    fetch_items: bool
    package_ids: tuple[str, ...] = ()


def _connect_jobs() -> sqlite3.Connection:
    conn = sqlite3.connect(JOB_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _load_active_ingest_jobs(conn: sqlite3.Connection) -> list[_ActiveJob]:
    rows = conn.execute(
        """
        SELECT id, kind, status, payload
        FROM jobs
                WHERE kind IN ('ingest', 'govinfo_bulk_batch')
                    AND status IN ('queued', 'running', 'retrying')
        ORDER BY created_at
        """
    ).fetchall()

    jobs: list[_ActiveJob] = []
    for row in rows:
        payload = json.loads(row["payload"])
        if row["kind"] == "govinfo_bulk_batch":
            jobs.append(
                _ActiveJob(
                    job_id=str(row["id"]),
                    status=str(row["status"]),
                    resource="GovInfo batch",
                    outdir=Path("."),
                    from_date=None,
                    to_date=None,
                    fetch_items=True,
                    package_ids=tuple(payload.get("job_ids", ())),
                )
            )
            continue
        resources = payload.get("resources") or []
        if not resources:
            continue
        resource = str(resources[0])
        jobs.append(
            _ActiveJob(
                job_id=str(row["id"]),
                status=str(row["status"]),
                resource=resource,
                outdir=Path(str(payload.get("outdir", "data/full_history")))
                / str(row["id"]),
                from_date=payload.get("from_date"),
                to_date=payload.get("to_date"),
                fetch_items=bool(payload.get("fetch_items", False)),
            )
        )
    return jobs


def _count_rows(db_path: Path, query: str, params: tuple[Any, ...] = ()) -> int:
    if not db_path.exists():
        return 0
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(query, params).fetchone()
    if not row:
        return 0
    return int(row[0] or 0)


def _hydrated_count(job: _ActiveJob) -> int:
    records_db = job.outdir / "records.sqlite3"
    return _count_rows(
        records_db,
        "SELECT count(*) FROM records WHERE resource = ?",
        (job.resource,),
    )


def _cached_list_count(job: _ActiveJob) -> int:
    cache_db = job.outdir / job.resource / "list_records.sqlite3"
    return _count_rows(cache_db, "SELECT count(*) FROM records")


def _fetch_bill_total(
    job: _ActiveJob,
    cache: dict[tuple[str | None, str | None], int | None],
) -> int | None:
    if job.resource != "bill" or not job.from_date or not job.to_date:
        return None

    key = (job.from_date, job.to_date)
    if key in cache:
        return cache[key]

    if not CONGRESS_API_KEY or not CONGRESS_API_URL:
        cache[key] = None
        return None

    try:
        response = requests.get(
            f"{CONGRESS_API_URL.rstrip('/')}/bill",
            params={
                "format": "json",
                "offset": 0,
                "limit": 1,
                "fromDateTime": job.from_date,
                "toDateTime": job.to_date,
            },
            headers={"x-api-key": CONGRESS_API_KEY},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        pagination = payload.get("pagination", {})
        total = int(pagination.get("count") or pagination.get("total") or 0)
        cache[key] = total
        return total
    except (KeyError, TypeError, ValueError, requests.RequestException):
        cache[key] = None
        return None


def get_ingest_progress() -> IngestProgressResponse:
    api_total_cache: dict[tuple[str | None, str | None], int | None] = {}

    with _connect_jobs() as conn:
        active_jobs = _load_active_ingest_jobs(conn)

    jobs: list[IngestProgressJob] = []
    total_hydrated = 0
    total_discovered = 0
    total_target = 0

    for job in active_jobs:
        if job.package_ids:
            status_query = (
                select(_JOBS_TABLE.c.status, func.count())
                .where(_JOBS_TABLE.c.id.in_(job.package_ids))
                .group_by(_JOBS_TABLE.c.status)
            )
            with _JOBS_ENGINE.connect() as batch_conn:
                status_rows = batch_conn.execute(status_query).all()
            package_counts = {
                str(status): int(count) for status, count in status_rows
            }
            hydrated = package_counts.get("succeeded", 0)
            discovered = hydrated + package_counts.get("running", 0)
            target = len(job.package_ids)
            api_total = None
        else:
            hydrated = _hydrated_count(job) if job.fetch_items else _cached_list_count(job)
            discovered = _cached_list_count(job)
            api_total = _fetch_bill_total(job, api_total_cache)

            if api_total and api_total > 0:
                target = max(hydrated, discovered, api_total)
            else:
                target = max(hydrated, discovered)

        discovered = min(target, discovered)
        remaining = max(0, target - hydrated)

        total_hydrated += hydrated
        total_discovered += discovered
        total_target += target

        jobs.append(
            IngestProgressJob(
                job_id=job.job_id,
                status=job.status,
                resource=job.resource,
                from_date=job.from_date,
                to_date=job.to_date,
                fetch_items=job.fetch_items,
                hydrated=hydrated,
                discovered=discovered,
                target=target,
                remaining=remaining,
            )
        )

    return IngestProgressResponse(
        hydrated=total_hydrated,
        discovered=total_discovered,
        target=total_target,
        remaining=max(0, total_target - total_hydrated),
        active_jobs=len(jobs),
        jobs=jobs,
    )


def _job_status_counts(conn: sqlite3.Connection, kind: str) -> JobStatusCounts:
    counts = {field: 0 for field in JobStatusCounts.model_fields}
    rows = conn.execute(
        "SELECT status, count(*) FROM jobs WHERE kind = ? GROUP BY status", (kind,)
    ).fetchall()
    for status, count in rows:
        if status in counts:
            counts[status] = int(count)
    return JobStatusCounts(**counts)


def _govinfo_coverage() -> GovInfoCoverage:
    if not _GOVINFO_REPORT.exists():
        return GovInfoCoverage(congress=118)
    try:
        report = json.loads(_GOVINFO_REPORT.read_text(encoding="utf-8"))
        counts = report.get("counts", {})
        return GovInfoCoverage(
            congress=int(report.get("congress", 118)),
            expected=int(report.get("expected_count", 0)),
            available=int(counts.get("available", 0)),
            pending=int(counts.get("pending", 0)),
            failed=int(counts.get("failed", 0)),
            not_available=int(counts.get("not_available", 0)),
            complete=bool(report.get("complete", False)),
            report_found=True,
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return GovInfoCoverage(congress=118, report_found=True)


def _staging_status() -> StagingStatus:
    status = StagingStatus(index=_STAGING_INDEX)
    try:
        client = get_opensearch_client(url=ES_LOCAL_URL, api_key=ES_LOCAL_API_KEY)
        status.connected = bool(client.ping())
        status.exists = bool(client.indices.exists(index=_STAGING_INDEX))
        if status.exists:
            status.documents = int(client.count(index=_STAGING_INDEX).get("count", 0))
        aliases = client.indices.get_alias(index="congress-legislation-read")
        status.production_alias_target = next(iter(aliases), None)
    except (TransportError, ValueError):
        return status
    return status


def get_admin_ingest_snapshot() -> AdminIngestSnapshot:
    coverage = _govinfo_coverage()
    with _connect_jobs() as conn:
        govinfo_jobs = _job_status_counts(conn, "govinfo_bulk")
        govinfo_batch_jobs = _job_status_counts(conn, "govinfo_bulk_batch")
        index_jobs = _job_status_counts(conn, "index")
        reconcile_jobs = _job_status_counts(conn, "reconcile")
    staging = _staging_status()
    return AdminIngestSnapshot(
        congress=coverage.congress,
        govinfo=coverage,
        govinfo_jobs=govinfo_jobs,
        govinfo_batch_jobs=govinfo_batch_jobs,
        index_jobs=index_jobs,
        reconcile_jobs=reconcile_jobs,
        staging=staging,
        ready_for_reconciliation=coverage.complete,
        ready_for_cutover=(
            coverage.complete
            and reconcile_jobs.succeeded > 0
            and staging.exists
            and staging.production_alias_target == "congress-legislation"
        ),
    )

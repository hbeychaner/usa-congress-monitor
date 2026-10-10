from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests
from elastic_transport import TransportError
from elasticsearch import Elasticsearch
from sqlalchemy import (
    Column,
    MetaData,
    String,
    Table,
    create_engine,
    func,
    select,
)
from sqlalchemy.engine import Connection, Engine

from cdm.config import AppConfig
from cdm.contracts.api import (
    AdminIngestSnapshot,
    BackfillProgress,
    GovInfoCoverage,
    IndexStatus,
    IngestProgressJob,
    IngestProgressResponse,
    JobStatusCounts,
    StagingStatus,
    SystemStatusResponse,
)

_JOBS_TABLE = Table(
    "jobs",
    MetaData(),
    Column("id", String),
    Column("kind", String),
    Column("status", String),
    Column("payload", String),
    Column("created_at", String),
    Column("updated_at", String),
)
_RECORDS_TABLE = Table(
    "records",
    MetaData(),
    Column("record_id", String),
    Column("resource", String),
    Column("payload", String),
)
_INGEST_WINDOWS_TABLE = Table(
    "ingest_windows",
    MetaData(),
    Column("job_id", String),
    Column("resource", String),
    Column("last_progress_at", String),
)

_PROGRESS_STALE_AFTER_SECONDS = 120


@dataclass
class _ActiveJob:
    job_id: str
    status: str
    resource: str
    congress: int | None
    outdir: Path
    from_date: str | None
    to_date: str | None
    fetch_items: bool


def _load_active_ingest_jobs(conn: Connection) -> list[_ActiveJob]:
    rows = (
        conn
        .execute(
            select(
                _JOBS_TABLE.c.id,
                _JOBS_TABLE.c.kind,
                _JOBS_TABLE.c.status,
                _JOBS_TABLE.c.payload,
            )
            # GovInfo bulk packages/batches are aggregated separately; listing
            # each of the ~211k queued packages here made this endpoint unusable.
            .where(_JOBS_TABLE.c.kind == "ingest")
            .where(_JOBS_TABLE.c.status.in_(("queued", "running", "retrying")))
            .order_by(_JOBS_TABLE.c.created_at)
        )
        .mappings()
        .all()
    )

    jobs: list[_ActiveJob] = []
    for row in rows:
        payload = json.loads(row["payload"])
        resources = payload.get("resources") or []
        if not resources:
            continue
        resource = str(resources[0])
        jobs.append(
            _ActiveJob(
                job_id=str(row["id"]),
                status=str(row["status"]),
                resource=resource,
                congress=(
                    int(payload["congress"])
                    if payload.get("congress") is not None
                    else None
                ),
                outdir=Path(str(payload.get("outdir", "data/full_history")))
                / str(row["id"]),
                from_date=payload.get("from_date"),
                to_date=payload.get("to_date"),
                fetch_items=bool(payload.get("fetch_items", False)),
            )
        )
    return jobs


def _count_rows(db_path: Path, statement) -> int:
    if not db_path.exists():
        return 0
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        row = conn.execute(statement).scalar_one_or_none()
    return int(row or 0)


def _hydrated_count(job: _ActiveJob) -> int:
    records_db = job.outdir / "records.sqlite3"
    return _count_rows(
        records_db,
        select(func.count())
        .select_from(_RECORDS_TABLE)
        .where(_RECORDS_TABLE.c.resource == job.resource),
    )


def _cached_list_count(job: _ActiveJob) -> int:
    cache_db = job.outdir / job.resource / "list_records.sqlite3"
    return _count_rows(cache_db, select(func.count()).select_from(_RECORDS_TABLE))


def _latest_progress_at(conn: Connection, job: _ActiveJob) -> str | None:
    return conn.execute(
        select(func.max(_INGEST_WINDOWS_TABLE.c.last_progress_at)).where(
            (_INGEST_WINDOWS_TABLE.c.job_id == job.job_id)
            & (_INGEST_WINDOWS_TABLE.c.resource == job.resource)
        )
    ).scalar_one_or_none()


def _job_activity(status: str, last_progress_at: str | None) -> str:
    if status in {"queued", "retrying"}:
        return "queued"
    if status != "running":
        return "idle"
    if not last_progress_at:
        return "waiting"
    try:
        heartbeat = datetime.fromisoformat(last_progress_at)
        if heartbeat.tzinfo is None:
            heartbeat = heartbeat.replace(tzinfo=UTC)
        age = (datetime.now(UTC) - heartbeat).total_seconds()
    except ValueError:
        return "waiting"
    return "continuing" if age <= _PROGRESS_STALE_AFTER_SECONDS else "stalled"


def _backfill_progress(conn: Connection) -> BackfillProgress | None:
    rows = conn.execute(
        select(_JOBS_TABLE.c.status, func.count())
        .where(_JOBS_TABLE.c.kind == "govinfo_bulk")
        .group_by(_JOBS_TABLE.c.status)
    ).all()
    counts = {str(status): int(count) for status, count in rows}
    total = sum(counts.values())
    if total == 0:
        return None
    succeeded = counts.get("succeeded", 0)
    pending = sum(counts.get(s, 0) for s in ("queued", "running", "retrying"))
    failed = counts.get("failed", 0) + counts.get("cancelled", 0)

    now = datetime.now(UTC)
    hour_ago = (now - timedelta(hours=1)).isoformat()
    rate = int(
        conn.execute(
            select(func.count())
            .where(_JOBS_TABLE.c.kind == "govinfo_bulk")
            .where(_JOBS_TABLE.c.status == "succeeded")
            .where(_JOBS_TABLE.c.updated_at >= hour_ago)
        ).scalar_one()
        or 0
    )
    batches_pending = int(
        conn.execute(
            select(func.count())
            .where(_JOBS_TABLE.c.kind == "govinfo_bulk_batch")
            .where(_JOBS_TABLE.c.status.in_(("queued", "running", "retrying")))
        ).scalar_one()
        or 0
    )
    eta: str | None = None
    if pending and rate > 0:
        eta = (now + timedelta(hours=pending / rate)).isoformat()
    return BackfillProgress(
        total=total,
        succeeded=succeeded,
        pending=pending,
        failed=failed,
        percent=round(succeeded / total * 100, 1),
        rate_per_hour=rate,
        eta=eta,
        batches_pending=batches_pending,
    )


def _job_status_counts(conn: Connection, kind: str) -> JobStatusCounts:
    counts = {field: 0 for field in JobStatusCounts.model_fields}
    rows = conn.execute(
        select(_JOBS_TABLE.c.status, func.count())
        .where(_JOBS_TABLE.c.kind == kind)
        .group_by(_JOBS_TABLE.c.status)
    ).all()
    for status, count in rows:
        if status in counts:
            counts[status] = int(count)
    return JobStatusCounts(**counts)


def _govinfo_coverage(conn: Connection) -> GovInfoCoverage:
    rows = conn.execute(
        select(_JOBS_TABLE.c.status, func.count())
        .where(_JOBS_TABLE.c.kind == "govinfo_bulk")
        .group_by(_JOBS_TABLE.c.status)
    ).all()
    counts = {str(status): int(count) for status, count in rows}
    available = counts.get("succeeded", 0)
    pending = sum(counts.get(status, 0) for status in ("queued", "running", "retrying"))
    failed = counts.get("failed", 0) + counts.get("cancelled", 0)
    expected = available + pending + failed + counts.get("not_available", 0)
    return GovInfoCoverage(
        congress=118,
        expected=expected,
        available=available,
        pending=pending,
        failed=failed,
        not_available=counts.get("not_available", 0),
        complete=pending == 0 and failed == 0,
        report_found=False,
    )


_STATUS_INDICES = (
    "congress-legislation",
    "congress-member",
    "congress-vote",
    "congress-amendment",
    "congress-committee",
    "congress-nomination",
    "congress-treaty",
)


class AdminService:
    """Operational status snapshots read from the job ledger and the search index."""

    def __init__(
        self, client: Elasticsearch, config: AppConfig, engine: Engine
    ) -> None:
        self._client = client
        self._config = config
        self._engine = engine

    def get_ingest_progress(self) -> IngestProgressResponse:
        api_total_cache: dict[tuple[str | None, str | None], int | None] = {}

        with self._engine.connect() as conn:
            active_jobs = _load_active_ingest_jobs(conn)
            backfill = _backfill_progress(conn)

        jobs: list[IngestProgressJob] = []
        total_hydrated = 0
        total_discovered = 0
        total_target = 0
        job_activities: list[str] = []
        latest_progress_at: str | None = None

        with self._engine.connect() as conn:
            progress_heartbeats = {
                job.job_id: _latest_progress_at(conn, job) for job in active_jobs
            }

        for job in active_jobs:
            job_progress_at = progress_heartbeats[job.job_id]
            job_activities.append(_job_activity(job.status, job_progress_at))
            if job_progress_at and (
                latest_progress_at is None or job_progress_at > latest_progress_at
            ):
                latest_progress_at = job_progress_at
            hydrated = (
                _hydrated_count(job) if job.fetch_items else _cached_list_count(job)
            )
            discovered = _cached_list_count(job)
            api_total = self._fetch_bill_total(job, api_total_cache)

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
                    congress=job.congress,
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
            activity=(
                "continuing"
                if "continuing" in job_activities
                else "stalled"
                if "stalled" in job_activities
                else "waiting"
                if "waiting" in job_activities
                else "queued"
                if "queued" in job_activities
                else "idle"
            ),
            last_progress_at=latest_progress_at,
            jobs=jobs,
            backfill=backfill,
        )

    def _fetch_bill_total(
        self,
        job: _ActiveJob,
        cache: dict[tuple[str | None, str | None], int | None],
    ) -> int | None:
        if job.resource != "bill" or not job.from_date or not job.to_date:
            return None

        key = (job.from_date, job.to_date)
        if key in cache:
            return cache[key]

        if not self._config.congress_api.congress_api_key or not self._config.congress_api.congress_api_url:
            cache[key] = None
            return None

        try:
            response = requests.get(
                f"{self._config.congress_api.congress_api_url.rstrip('/')}/bill",
                params={
                    "format": "json",
                    "offset": 0,
                    "limit": 1,
                    "fromDateTime": job.from_date,
                    "toDateTime": job.to_date,
                },
                headers={"x-api-key": self._config.congress_api.congress_api_key},
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

    def _staging_status(self) -> StagingStatus:
        status = StagingStatus(index=self._config.elastic.staging_index)
        try:
            status.connected = bool(self._client.ping())
            status.exists = bool(self._client.indices.exists(index=self._config.elastic.staging_index))
            if status.exists:
                status.documents = int(self._client.count(index=self._config.elastic.staging_index).get("count", 0))
            aliases = self._client.indices.get_alias(index="congress-legislation-read")
            status.production_alias_target = next(iter(aliases), None)
        except (TransportError, ValueError):
            return status
        return status

    def get_admin_ingest_snapshot(self) -> AdminIngestSnapshot:
        with self._engine.connect() as conn:
            coverage = _govinfo_coverage(conn)
            govinfo_jobs = _job_status_counts(conn, "govinfo_bulk")
            govinfo_batch_jobs = _job_status_counts(conn, "govinfo_bulk_batch")
            index_jobs = _job_status_counts(conn, "index")
            reconcile_jobs = _job_status_counts(conn, "reconcile")
        staging = self._staging_status()
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

    def get_system_status(self) -> SystemStatusResponse:
        with self._engine.connect() as conn:
            kinds = [
                str(kind)
                for (kind,) in conn.execute(
                    select(_JOBS_TABLE.c.kind).distinct().order_by(_JOBS_TABLE.c.kind)
                ).all()
                if kind
            ]
            jobs = {kind: _job_status_counts(conn, kind) for kind in kinds}
        indices: list[IndexStatus] = []
        connected = False
        try:
            connected = bool(self._client.ping())
            if connected:
                for name in _STATUS_INDICES:
                    alias = f"{name}-read"
                    if not self._client.indices.exists(index=alias):
                        continue
                    count = int(self._client.count(index=alias).get("count", 0))
                    indices.append(IndexStatus(name=name, documents=count))
        except (TransportError, ValueError):
            connected = False
        return SystemStatusResponse(
            search_connected=connected,
            indices=indices,
            jobs=jobs,
            generated_at=datetime.now(UTC).isoformat(),
        )

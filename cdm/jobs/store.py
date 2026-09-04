"""SQLAlchemy-backed job records for Celery-dispatched work."""

from __future__ import annotations

import fcntl
import json
from contextlib import contextmanager
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    select,
    update,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool


class JobKind(StrEnum):
    INGEST = "ingest"
    INDEX = "index"
    GOVINFO_BULK = "govinfo_bulk"
    GOVINFO_BULK_BATCH = "govinfo_bulk_batch"
    RECONCILE = "reconcile"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRYING = "retrying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CoverageStage(StrEnum):
    DISCOVERY = "discovery"
    HYDRATION = "hydration"


_METADATA = MetaData()
_JOBS = Table(
    "jobs",
    _METADATA,
    Column("id", String, primary_key=True),
    Column("kind", String, nullable=False),
    Column("idempotency_key", String, nullable=False, unique=True),
    Column("payload", Text, nullable=False),
    Column("status", String, nullable=False),
    Column("attempts", Integer, nullable=False, default=0),
    Column("last_error", Text),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
    Column("started_at", String),
    Column("finished_at", String),
)
_INGEST_WINDOWS = Table(
    "ingest_windows",
    _METADATA,
    Column("job_id", String, primary_key=True),
    Column("resource", String, primary_key=True),
    Column("window_start", String),
    Column("window_end", String),
    Column("congress", Integer),
    Column("status", String, nullable=False),
    Column("fetch_items", Boolean, nullable=False, default=False),
    Column("discovered_count", Integer, nullable=False, default=0),
    Column("hydrated_count", Integer, nullable=False, default=0),
    Column("target_count", Integer, nullable=False, default=0),
    Column("checkpoint_offset", Integer),
    Column("last_started_at", String),
    Column("last_progress_at", String),
    Column("completed_at", String),
    Column("last_error", Text),
)

_JOBS_STATUS_INDEX = "jobs_status_idx"
_INGEST_WINDOWS_PERIOD_INDEX = "ingest_windows_period_idx"
_INGEST_WINDOWS_STATUS_INDEX = "ingest_windows_status_idx"


# Index names are declared separately because SQLAlchemy's Table metadata does
# not need to change the existing SQLite schema during this migration.
from sqlalchemy import Index, event

Index(_JOBS_STATUS_INDEX, _JOBS.c.status)
Index(
    _INGEST_WINDOWS_PERIOD_INDEX,
    _INGEST_WINDOWS.c.resource,
    _INGEST_WINDOWS.c.window_start,
    _INGEST_WINDOWS.c.window_end,
)
Index(_INGEST_WINDOWS_STATUS_INDEX, _INGEST_WINDOWS.c.status)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_dict(row: Any) -> dict:
    return dict(row._mapping)


class JobStore:
    """Persist job lifecycle independently of the RabbitMQ result backend."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.engine: Engine = create_engine(
            f"sqlite:///{self.path}",
            connect_args={"timeout": 60, "check_same_thread": False},
            poolclass=NullPool,
        )
        self._transaction_lock_path = self.path.with_name(
            f".{self.path.name}.transaction.lock"
        )
        event.listen(
            self.engine,
            "connect",
            lambda connection, _: (
                connection.execute("PRAGMA busy_timeout=60000"),
                connection.execute("PRAGMA journal_mode=WAL"),
                connection.execute("PRAGMA synchronous=NORMAL"),
            ),
        )
        init_lock_path = self.path.with_name(f".{self.path.name}.init.lock")
        with init_lock_path.open("w") as init_lock:
            fcntl.flock(init_lock.fileno(), fcntl.LOCK_EX)
            _METADATA.create_all(self.engine)
            with self._transaction_lock(), self.engine.begin() as connection:
                rows = connection.execute(
                    select(
                        _JOBS.c.id,
                        _JOBS.c.payload,
                        _JOBS.c.status,
                        _JOBS.c.created_at,
                    ).where(_JOBS.c.kind == JobKind.INGEST.value)
                )
                for row in rows:
                    job_id = str(row.id)
                    self._register_ingest_windows(
                        connection,
                        job_id,
                        json.loads(row.payload),
                        str(row.created_at),
                        str(row.status),
                    )
                    connection.execute(
                        update(_INGEST_WINDOWS)
                        .where(_INGEST_WINDOWS.c.job_id == job_id)
                        .where(_INGEST_WINDOWS.c.status != str(row.status))
                        .values(status=str(row.status))
                    )
            fcntl.flock(init_lock.fileno(), fcntl.LOCK_UN)

    @contextmanager
    def _transaction_lock(self):
        with self._transaction_lock_path.open("w") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def create(self, kind: str, idempotency_key: str, payload: dict[str, Any]) -> dict:
        now = _now()
        job_id = idempotency_key
        with self._transaction_lock(), self.engine.begin() as connection:
            connection.execute(
                sqlite_insert(_JOBS)
                .prefix_with("OR IGNORE")
                .values(
                    id=job_id,
                    kind=kind,
                    idempotency_key=idempotency_key,
                    payload=json.dumps(payload),
                    status=JobStatus.QUEUED.value,
                    created_at=now,
                    updated_at=now,
                )
            )
            if kind == JobKind.INGEST:
                self._register_ingest_windows(
                    connection, job_id, payload, now, JobStatus.QUEUED.value
                )
            row = (
                connection
                .execute(select(_JOBS).where(_JOBS.c.id == job_id))
                .mappings()
                .one()
            )
        result = dict(row)
        result["payload"] = json.loads(result["payload"])
        return result

    def create_govinfo_bulk_job(self, package: Any, *, outdir: Path | str) -> dict:
        """Create an idempotent durable job for one GovInfo package."""
        payload = {
            "collection": str(package.collection),
            "congress": int(package.congress),
            "measure_type": str(package.measure_type),
            "package_id": str(package.package_id),
            "url": str(package.url),
            "session": package.session,
            "version_code": package.version_code,
            "outdir": str(outdir),
        }
        idempotency_key = "govinfo:" + ":".join((
            payload["collection"],
            str(payload["congress"]),
            payload["measure_type"],
            payload["package_id"],
        ))
        return self.create(JobKind.GOVINFO_BULK.value, idempotency_key, payload)

    @staticmethod
    def _register_ingest_windows(
        connection: Any,
        job_id: str,
        payload: dict[str, Any],
        now: str,
        status: str,
    ) -> None:
        for resource in payload.get("resources") or []:
            connection.execute(
                sqlite_insert(_INGEST_WINDOWS)
                .prefix_with("OR IGNORE")
                .values(
                    job_id=job_id,
                    resource=str(resource),
                    window_start=payload.get("from_date"),
                    window_end=payload.get("to_date"),
                    congress=payload.get("congress"),
                    status=status,
                    fetch_items=bool(payload.get("fetch_items", False)),
                    last_progress_at=now,
                )
            )

    def get(self, job_id: str) -> dict:
        with self.engine.connect() as connection:
            row = (
                connection
                .execute(select(_JOBS).where(_JOBS.c.id == job_id))
                .mappings()
                .first()
            )
        if row is None:
            raise KeyError(f"Unknown job {job_id}")
        result = dict(row)
        result["payload"] = json.loads(result["payload"])
        return result

    def mark_running(self, job_id: str, *, update_windows: bool = True) -> dict | None:
        """Atomically claim a job for execution, returning ``None`` if already claimed.

        RUNNING is intentionally excluded from the claimable source statuses so
        a duplicate message delivered for a job that's already in progress (or
        finished) becomes a safe no-op instead of a second concurrent run.

        ``update_windows`` is ``False`` for package jobs (e.g. GovInfo bulk)
        that have no corresponding ``_INGEST_WINDOWS`` row.
        """
        now = _now()
        with self._transaction_lock(), self.engine.begin() as connection:
            result = connection.execute(
                update(_JOBS)
                .where(
                    (_JOBS.c.id == job_id)
                    & _JOBS.c.status.in_([
                        JobStatus.QUEUED.value,
                        JobStatus.RETRYING.value,
                        JobStatus.FAILED.value,
                    ])
                )
                .values(
                    status=JobStatus.RUNNING.value,
                    attempts=_JOBS.c.attempts + 1,
                    started_at=now,
                    updated_at=now,
                    last_error=None,
                )
            )
            if result.rowcount != 1:
                return None
            if update_windows:
                connection.execute(
                    update(_INGEST_WINDOWS)
                    .where(_INGEST_WINDOWS.c.job_id == job_id)
                    .values(
                        status=JobStatus.RUNNING.value,
                        last_started_at=now,
                        last_progress_at=now,
                    )
                )
        return self.get(job_id)

    def mark_succeeded(self, job_id: str) -> dict:
        now = _now()
        with self._transaction_lock(), self.engine.begin() as connection:
            connection.execute(
                update(_JOBS)
                .where(_JOBS.c.id == job_id)
                .values(
                    status=JobStatus.SUCCEEDED.value,
                    updated_at=now,
                    finished_at=now,
                )
            )
            connection.execute(
                update(_INGEST_WINDOWS)
                .where(_INGEST_WINDOWS.c.job_id == job_id)
                .values(
                    status=JobStatus.SUCCEEDED.value,
                    completed_at=now,
                    last_progress_at=now,
                )
            )
        return self.get(job_id)

    def mark_failed(self, job_id: str, error: str) -> dict:
        now = _now()
        with self._transaction_lock(), self.engine.begin() as connection:
            connection.execute(
                update(_JOBS)
                .where(_JOBS.c.id == job_id)
                .values(
                    status=JobStatus.FAILED.value,
                    last_error=error,
                    updated_at=now,
                )
            )
            connection.execute(
                update(_INGEST_WINDOWS)
                .where(_INGEST_WINDOWS.c.job_id == job_id)
                .values(
                    status=JobStatus.FAILED.value,
                    last_error=error,
                    last_progress_at=now,
                )
            )
        return self.get(job_id)

    def mark_retrying(self, job_id: str, error: str) -> dict:
        now = _now()
        with self._transaction_lock(), self.engine.begin() as connection:
            connection.execute(
                update(_JOBS)
                .where(_JOBS.c.id == job_id)
                .values(
                    status=JobStatus.RETRYING.value,
                    last_error=error,
                    updated_at=now,
                )
            )
            connection.execute(
                update(_INGEST_WINDOWS)
                .where(_INGEST_WINDOWS.c.job_id == job_id)
                .values(
                    status=JobStatus.RETRYING.value,
                    last_error=error,
                    last_progress_at=now,
                )
            )
        return self.get(job_id)

    def coverage(self, resource: str | None = None) -> list[dict]:
        statement = select(_INGEST_WINDOWS).order_by(
            _INGEST_WINDOWS.c.window_start,
            _INGEST_WINDOWS.c.window_end,
            _INGEST_WINDOWS.c.resource,
        )
        if resource:
            statement = statement.where(_INGEST_WINDOWS.c.resource == resource)
        with self.engine.connect() as connection:
            return [_row_dict(row) for row in connection.execute(statement)]

    def update_coverage(self, job_id: str, resource: str, **fields: Any) -> None:
        allowed = {
            "discovered_count": _INGEST_WINDOWS.c.discovered_count,
            "hydrated_count": _INGEST_WINDOWS.c.hydrated_count,
            "target_count": _INGEST_WINDOWS.c.target_count,
            "checkpoint_offset": _INGEST_WINDOWS.c.checkpoint_offset,
            "last_progress_at": _INGEST_WINDOWS.c.last_progress_at,
            "last_error": _INGEST_WINDOWS.c.last_error,
        }
        values = {
            allowed[key]: value for key, value in fields.items() if key in allowed
        }
        if not values:
            return
        values.setdefault(_INGEST_WINDOWS.c.last_progress_at, _now())
        with self._transaction_lock(), self.engine.begin() as connection:
            connection.execute(
                update(_INGEST_WINDOWS)
                .where(
                    (_INGEST_WINDOWS.c.job_id == job_id)
                    & (_INGEST_WINDOWS.c.resource == resource)
                )
                .values(values)
            )

    def requeue(self, job_id: str) -> dict:
        """Move a job back to QUEUED, also refreshing an already-QUEUED job's timestamp.

        Refreshing the timestamp on a no-op QUEUED->QUEUED transition lets
        callers rate-limit redispatch of the same stale job via ``updated_at``.
        """
        now = _now()
        with self._transaction_lock(), self.engine.begin() as connection:
            connection.execute(
                update(_JOBS)
                .where(
                    (_JOBS.c.id == job_id)
                    & _JOBS.c.status.in_([
                        JobStatus.QUEUED.value,
                        JobStatus.FAILED.value,
                        JobStatus.RUNNING.value,
                        JobStatus.RETRYING.value,
                    ])
                )
                .values(status=JobStatus.QUEUED.value, updated_at=now)
            )
        return self.get(job_id)

    def _fetch(self, statement: Any) -> list[dict]:
        """Execute a ``select(_JOBS)`` statement and decode payloads in one round trip.

        Avoids the N+1 pattern of selecting ids then calling ``get()`` per row.
        """
        with self.engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        results = []
        for row in rows:
            result = dict(row)
            result["payload"] = json.loads(result["payload"])
            results.append(result)
        return results

    def failed(self, kind: str | None = None) -> list[dict]:
        statement = select(_JOBS).where(_JOBS.c.status == JobStatus.FAILED.value)
        if kind:
            statement = statement.where(_JOBS.c.kind == kind)
        statement = statement.order_by(_JOBS.c.updated_at)
        return self._fetch(statement)

    def stale_active(self, cutoff: str) -> list[dict]:
        """Return RUNNING/RETRYING jobs stranded past ``cutoff`` (e.g. a worker crash)."""
        statement = (
            select(_JOBS)
            .where(
                _JOBS.c.status.in_([JobStatus.RUNNING.value, JobStatus.RETRYING.value])
            )
            .where(_JOBS.c.updated_at < cutoff)
            .order_by(_JOBS.c.updated_at)
        )
        return self._fetch(statement)

    def stale_queued(
        self, kinds: tuple[str, ...], cutoff: str, limit: int
    ) -> list[dict]:
        """Return up to ``limit`` QUEUED jobs of ``kinds`` stale past ``cutoff``.

        This is a rare safety net for dispatch messages lost to broker hiccups;
        callers should keep ``limit`` small so a large backlog can't flood the
        broker with duplicate messages in a single sweep.
        """
        statement = (
            select(_JOBS)
            .where(_JOBS.c.status == JobStatus.QUEUED.value)
            .where(_JOBS.c.kind.in_(kinds))
            .where(_JOBS.c.updated_at < cutoff)
            .order_by(_JOBS.c.updated_at)
            .limit(limit)
        )
        return self._fetch(statement)

    def queued(self, kind: str | None = None) -> list[dict]:
        statement = select(_JOBS).where(_JOBS.c.status == JobStatus.QUEUED.value)
        if kind:
            statement = statement.where(_JOBS.c.kind == kind)
        statement = statement.order_by(_JOBS.c.created_at)
        return self._fetch(statement)

    def jobs(self, kind: str | None = None) -> list[dict]:
        """Return durable jobs ordered from newest to oldest."""
        statement = select(_JOBS).order_by(_JOBS.c.created_at.desc())
        if kind:
            statement = statement.where(_JOBS.c.kind == kind)
        return self._fetch(statement)

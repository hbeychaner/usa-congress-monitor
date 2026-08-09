"""SQLite-backed job records for Celery-dispatched work."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    payload TEXT NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS jobs_status_idx ON jobs(status);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


class JobStore:
    """Persist job lifecycle independently of the RabbitMQ result backend."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def create(self, kind: str, idempotency_key: str, payload: dict[str, Any]) -> dict:
        now = _now()
        job_id = idempotency_key
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO jobs
                (id, kind, idempotency_key, payload, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'queued', ?, ?)
                """,
                (job_id, kind, idempotency_key, json.dumps(payload), now, now),
            )
        return self.get(job_id)

    def get(self, job_id: str) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown job {job_id}")
        result = dict(row)
        result["payload"] = json.loads(result["payload"])
        return result

    def mark_running(self, job_id: str) -> dict:
        now = _now()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = 'running', attempts = attempts + 1,
                    started_at = ?, updated_at = ?, last_error = NULL
                WHERE id = ? AND status IN ('queued', 'running', 'failed')
                """,
                (now, now, job_id),
            )
        return self.get(job_id)

    def mark_succeeded(self, job_id: str) -> dict:
        now = _now()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = 'succeeded', updated_at = ?, finished_at = ?
                WHERE id = ?
                """,
                (now, now, job_id),
            )
        return self.get(job_id)

    def mark_failed(self, job_id: str, error: str) -> dict:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = 'failed', last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (error, _now(), job_id),
            )
        return self.get(job_id)

    def queued(self, kind: str | None = None) -> list[dict]:
        query = "SELECT id FROM jobs WHERE status = 'queued'"
        parameters: tuple[Any, ...] = ()
        if kind:
            query += " AND kind = ?"
            parameters = (kind,)
        query += " ORDER BY created_at"
        with self._connect() as connection:
            ids = connection.execute(query, parameters).fetchall()
        return [self.get(row["id"]) for row in ids]

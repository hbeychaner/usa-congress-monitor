"""Durable, compact archives for fetched ingest records."""

from __future__ import annotations

import hashlib
import json
import threading
import zlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import (
    BLOB,
    Column,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    event,
    select,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

_ARCHIVE_METADATA = MetaData()
_ARCHIVED_RECORDS = Table(
    "records",
    _ARCHIVE_METADATA,
    Column("resource", String, primary_key=True),
    Column("record_id", String, primary_key=True),
    Column("payload", BLOB, nullable=False),
)
_CACHED_RECORDS = Table(
    "records",
    MetaData(),
    Column(
        "page_offset",
        Integer,
        primary_key=True,
        nullable=True,
    ),
    Column(
        "record_id",
        String,
        primary_key=True,
        nullable=True,
    ),
    Column("payload", BLOB, nullable=False),
)
_QUARANTINED_RECORDS = Table(
    "quarantined_records",
    MetaData(),
    Column("failure_id", String, primary_key=True),
    Column("resource", String, nullable=False),
    Column("record_id", String, nullable=True),
    Column("source_url", String, nullable=True),
    Column("payload", BLOB, nullable=False),
    Column("error", String, nullable=False),
    Column("captured_at", String, nullable=False),
)


def _archive_engine(path: Path) -> Engine:
    engine = create_engine(f"sqlite:///{path}", connect_args={"timeout": 30})
    event.listen(
        engine,
        "connect",
        lambda connection, _: (
            connection.execute("PRAGMA journal_mode=DELETE"),
            connection.execute("PRAGMA synchronous=NORMAL"),
        ),
    )
    return engine


class SQLiteRecordArchive:
    """Store one compressed, deduplicated record per resource in SQLite."""

    def __init__(self, root: Path, attempt: int) -> None:
        del attempt
        self.root = root
        self.path = root / "records.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.engine = _archive_engine(self.path)
        _ARCHIVE_METADATA.create_all(self.engine)

    @staticmethod
    def _record_id(record: dict[str, Any]) -> str:
        identity = record.get("id") or record.get("url")
        # Legacy bill lists reuse the same canonical key for distinct entries.
        if (
            record.get("introduced_date")
            and isinstance(identity, str)
            and identity.startswith("bill:")
            and not identity.endswith(f":{record['introduced_date']}")
        ):
            identity = f"{identity}:{record['introduced_date']}"
        if identity is not None:
            return str(identity)
        encoded = json.dumps(record, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(encoded.encode()).hexdigest()

    def write(
        self,
        resource: str,
        record: dict[str, Any],
        *,
        record_id: str | None = None,
    ) -> None:
        payload = zlib.compress(
            json.dumps(record, ensure_ascii=True, separators=(",", ":")).encode(),
            level=6,
        )
        with self._lock, self.engine.begin() as connection:
            connection.execute(
                sqlite_insert(_ARCHIVED_RECORDS)
                .prefix_with("OR IGNORE")
                .values(
                    resource=resource,
                    record_id=record_id or self._record_id(record),
                    payload=payload,
                )
            )

    def write_many(self, resource: str, records: list[dict[str, Any]]) -> None:
        rows = [
            (
                resource,
                self._record_id(record),
                zlib.compress(
                    json.dumps(
                        record, ensure_ascii=True, separators=(",", ":")
                    ).encode(),
                    level=6,
                ),
            )
            for record in records
        ]
        with self._lock, self.engine.begin() as connection:
            connection.execute(
                sqlite_insert(_ARCHIVED_RECORDS)
                .prefix_with("OR IGNORE")
                .values(
                    [
                        dict(zip(("resource", "record_id", "payload"), row))
                        for row in rows
                    ]
                )
            )

    def ids(self, resource: str) -> set[str]:
        with self.engine.connect() as connection:
            return set(
                connection.execute(
                    select(_ARCHIVED_RECORDS.c.record_id).where(
                        _ARCHIVED_RECORDS.c.resource == resource
                    )
                ).scalars()
            )

    def records(self, resource: str) -> list[dict[str, Any]]:
        """Return archived records for *resource* for deterministic replay."""
        with self.engine.connect() as connection:
            payloads = connection.execute(
                select(_ARCHIVED_RECORDS.c.payload)
                .where(_ARCHIVED_RECORDS.c.resource == resource)
                .order_by(_ARCHIVED_RECORDS.c.record_id)
            ).scalars()
        return [json.loads(zlib.decompress(payload)) for payload in payloads]

    def contains(self, resource: str, record_id: str) -> bool:
        with self.engine.connect() as connection:
            return (
                connection.execute(
                    select(_ARCHIVED_RECORDS.c.record_id)
                    .where(_ARCHIVED_RECORDS.c.resource == resource)
                    .where(_ARCHIVED_RECORDS.c.record_id == record_id)
                ).first()
                is not None
            )


class SQLiteListCache:
    """Store resumable list pages as compressed, deduplicated rows."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.engine = _archive_engine(self.path)
        _CACHED_RECORDS.metadata.create_all(self.engine)

    def write(self, offset: int, record: dict[str, Any]) -> None:
        payload = zlib.compress(
            json.dumps(record, ensure_ascii=True, separators=(",", ":")).encode(),
            level=6,
        )
        record_id = SQLiteRecordArchive._record_id(record)
        with self._lock, self.engine.begin() as connection:
            connection.execute(
                sqlite_insert(_CACHED_RECORDS)
                .prefix_with("OR IGNORE")
                .values(page_offset=offset, record_id=record_id, payload=payload)
            )

    def write_many(self, rows: list[tuple[int, dict[str, Any]]]) -> None:
        values = [
            (
                offset,
                SQLiteRecordArchive._record_id(record),
                zlib.compress(
                    json.dumps(
                        record, ensure_ascii=True, separators=(",", ":")
                    ).encode(),
                    level=6,
                ),
            )
            for offset, record in rows
        ]
        with self._lock, self.engine.begin() as connection:
            for offset, record_id, payload in values:
                connection.execute(
                    sqlite_insert(_CACHED_RECORDS)
                    .prefix_with("OR IGNORE")
                    .values(
                        page_offset=offset,
                        record_id=record_id,
                        payload=payload,
                    )
                )

    def contains(self, offset: int, record: dict[str, Any]) -> bool:
        record_id = SQLiteRecordArchive._record_id(record)
        with self.engine.connect() as connection:
            return (
                connection.execute(
                    select(_CACHED_RECORDS.c.record_id)
                    .where(_CACHED_RECORDS.c.page_offset == offset)
                    .where(_CACHED_RECORDS.c.record_id == record_id)
                ).first()
                is not None
            )

    def load(self, model_cls: type, next_offset: int) -> list:
        models = []
        seen_ids: set[str] = set()
        statement = select(_CACHED_RECORDS.c.record_id, _CACHED_RECORDS.c.payload)
        if next_offset != -1:
            statement = statement.where(_CACHED_RECORDS.c.page_offset < next_offset)
        statement = statement.order_by(_CACHED_RECORDS.c.page_offset)
        with self.engine.connect() as connection:
            for record_id, payload in connection.execute(statement):
                if record_id in seen_ids:
                    continue
                models.append(
                    # Cached payloads are snake_case model dumps; without
                    # by_name, alias-only fields silently reset to defaults.
                    model_cls.model_validate(
                        json.loads(zlib.decompress(payload)), by_name=True
                    )
                )
                seen_ids.add(record_id)
        return models


class SQLiteQuarantineArchive:
    """Store raw payloads that failed model validation for later replay."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = root / "quarantine.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.engine = _archive_engine(self.path)
        _QUARANTINED_RECORDS.metadata.create_all(self.engine)

    def write(
        self,
        resource: str,
        record: dict[str, Any],
        *,
        error: str,
        source_url: str | None = None,
        record_id: str | None = None,
    ) -> None:
        encoded = json.dumps(record, ensure_ascii=True, separators=(",", ":"))
        payload = zlib.compress(encoded.encode(), level=6)
        stable_id = record_id or SQLiteRecordArchive._record_id(record)
        failure_id = hashlib.sha256(
            f"{resource}:{stable_id}:{error}".encode()
        ).hexdigest()
        with self._lock, self.engine.begin() as connection:
            connection.execute(
                sqlite_insert(_QUARANTINED_RECORDS)
                .prefix_with("OR IGNORE")
                .values(
                    failure_id=failure_id,
                    resource=resource,
                    record_id=stable_id,
                    source_url=source_url,
                    payload=payload,
                    error=error,
                    captured_at=datetime.now(UTC).isoformat(),
                )
            )

    def records(self, resource: str | None = None) -> list[dict[str, Any]]:
        """Return quarantined payloads and validation metadata for replay."""
        statement = select(
            _QUARANTINED_RECORDS.c.resource,
            _QUARANTINED_RECORDS.c.record_id,
            _QUARANTINED_RECORDS.c.source_url,
            _QUARANTINED_RECORDS.c.payload,
            _QUARANTINED_RECORDS.c.error,
            _QUARANTINED_RECORDS.c.captured_at,
        ).order_by(_QUARANTINED_RECORDS.c.failure_id)
        if resource is not None:
            statement = statement.where(_QUARANTINED_RECORDS.c.resource == resource)
        with self.engine.connect() as connection:
            rows = connection.execute(statement)
            return [
                {
                    "resource": row.resource,
                    "record_id": row.record_id,
                    "source_url": row.source_url,
                    "payload": json.loads(zlib.decompress(row.payload)),
                    "error": row.error,
                    "captured_at": row.captured_at,
                }
                for row in rows
            ]


# Compatibility name for integrations that imported the old archive class.
JsonlRecordArchive = SQLiteRecordArchive

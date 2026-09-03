"""Durable Redis Stream handoff for ingest records."""

from __future__ import annotations

import json
import os
from typing import Any

from redis import Redis
from redis.exceptions import ResponseError


class RedisRecordStream:
    """Publish and consume records with Redis Streams consumer groups."""

    def __init__(self, client: Redis, stream: str, *, maxlen: int = 1_000_000) -> None:
        self.client = client
        self.stream = stream
        self.maxlen = maxlen

    @staticmethod
    def stream_name(job_id: str, resource: str) -> str:
        return f"congress:ingest:{job_id}:{resource}"

    def publish(
        self,
        resource: str,
        record: dict[str, Any],
        ingest_metadata: dict[str, Any] | None = None,
    ) -> str:
        fields: dict[str, Any] = {
            "resource": resource,
            "record": json.dumps(record, default=str),
        }
        if ingest_metadata is not None:
            fields["ingest_metadata"] = json.dumps(ingest_metadata, default=str)
        entry_id = self.client.xadd(
            self.stream,
            fields,
            maxlen=self.maxlen,
            approximate=True,
        )
        return entry_id.decode() if isinstance(entry_id, bytes) else entry_id

    def ensure_group(self, group: str) -> None:
        try:
            self.client.xgroup_create(self.stream, group, id="0-0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def read_batch(
        self,
        group: str,
        *,
        count: int,
        consumer: str | None = None,
        block_ms: int = 1000,
        min_idle_ms: int = 60_000,
    ) -> list[tuple[str, dict[str, Any]]]:
        if count < 1:
            raise ValueError("count must be positive")
        consumer = consumer or f"consumer-{os.getpid()}"
        self.ensure_group(group)
        pending = self.client.xautoclaim(
            self.stream,
            group,
            consumer,
            min_idle_time=min_idle_ms,
            start_id="0-0",
            count=count,
        )
        records = self._decode_entries(pending[1])
        if len(records) >= count:
            return records[:count]
        fresh = self.client.xreadgroup(
            group,
            consumer,
            {self.stream: ">"},
            count=count - len(records),
            block=block_ms,
        )
        for _, entries in fresh:
            records.extend(self._decode_entries(entries))
        return records

    def acknowledge(self, group: str, entry_ids: list[str]) -> int:
        if not entry_ids:
            return 0
        return int(self.client.xack(self.stream, group, *entry_ids))

    @staticmethod
    def _decode_entries(
        entries: list[tuple[Any, dict[Any, Any]]],
    ) -> list[tuple[str, dict[str, Any]]]:
        decoded: list[tuple[str, dict[str, Any]]] = []
        for entry_id, fields in entries:
            normalized = {
                (key.decode() if isinstance(key, bytes) else key): value
                for key, value in fields.items()
            }
            record = json.loads(normalized["record"])
            resource = normalized["resource"]
            ingest_metadata = None
            if normalized.get("ingest_metadata"):
                ingest_metadata = json.loads(normalized["ingest_metadata"])
                if not isinstance(ingest_metadata, dict):
                    ingest_metadata = None
            decoded.append(
                (
                    entry_id.decode() if isinstance(entry_id, bytes) else entry_id,
                    {
                        "resource": resource,
                        "record": record,
                        "ingest_metadata": ingest_metadata,
                    },
                )
            )
        return decoded

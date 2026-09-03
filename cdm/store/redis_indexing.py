"""Index records from Redis Streams with acknowledge-after-bulk semantics."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from cdm.ingest.redis_stream import RedisRecordStream
from cdm.store.indexer import to_document
from cdm.store.mapping_validation import validate_document
from cdm.store.opensearch import bulk_upsert


@dataclass
class RedisIndexingRunner:
    redis_client: Any
    opensearch_client: Any
    stream: str
    resource: str
    batch_size: int = 500
    consumer_group: str = "congress-indexers"
    consumer: str = ""
    preserve_raw: bool = False
    target_index: str | None = None
    replace: bool = False

    def run(self) -> dict:
        if self.batch_size < 1:
            raise ValueError("batch_size must be positive")
        stream = RedisRecordStream(self.redis_client, self.stream)
        consumer = self.consumer or f"worker-{os.getpid()}"
        indexed = 0
        batches = 0

        while True:
            entries = stream.read_batch(
                self.consumer_group,
                count=self.batch_size,
                consumer=consumer,
            )
            if not entries:
                break
            documents = [
                to_document(
                    entry["record"],
                    self.resource,
                    preserve_raw=self.preserve_raw,
                    ingest_metadata=entry.get("ingest_metadata"),
                )
                for _, entry in entries
            ]
            for document in documents:
                validate_document(document, self.resource)
            result = bulk_upsert(
                self.opensearch_client,
                self.resource,
                documents,
                target_index=self.target_index,
                replace=self.replace,
            )
            if result.get("errors"):
                raise RuntimeError(
                    "OpenSearch bulk indexing failed for Redis stream "
                    f"{self.stream}: {result.get('error_details', [])}"
                )
            stream.acknowledge(
                self.consumer_group,
                [entry_id for entry_id, _ in entries],
            )
            indexed += int(result.get("updated", 0))
            batches += 1

        return {
            "stream": self.stream,
            "resource": self.resource,
            "indexed": indexed,
            "batches": batches,
            "pending": int(
                self.redis_client.xpending(self.stream, self.consumer_group)["pending"]
            ),
            "stream_length": int(self.redis_client.xlen(self.stream)),
            "status": "completed",
        }

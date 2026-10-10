"""Index several Redis streams through shared bulk requests."""

from __future__ import annotations

import os
from typing import cast

from elasticsearch import Elasticsearch
from pydantic import BaseModel
from redis import Redis

from cdm.ingest.redis_stream import RedisRecordStream, StreamEntry
from cdm.jobs.payloads import IndexPayload
from cdm.store.indexer import to_document
from cdm.store.mapping_validation import validate_document
from cdm.store.opensearch import bulk_upsert


class IndexOutcome(BaseModel):
    stream: str
    resource: str
    indexed: int
    batches: int
    pending: int
    stream_length: int
    status: str = "completed"
    replayed_from_archive: int | None = None


class StreamIndexer:
    """Drains job streams, flushing one bulk per ``batch_docs`` documents.

    Streams are acknowledged only after their bulk succeeds. A failed bulk
    fails every job that contributed to it and leaves those entries pending
    for redelivery.
    """

    def __init__(
        self,
        redis_client: Redis,
        opensearch_client: Elasticsearch,
        *,
        batch_docs: int,
        default_group: str,
    ) -> None:
        self.redis = redis_client
        self.client = opensearch_client
        self.batch_docs = batch_docs
        self._default_group = default_group

    def group(self, payload: IndexPayload) -> str:
        return payload.consumer_group or self._default_group

    def index(
        self,
        payloads: dict[str, IndexPayload],
        *,
        resource: str,
        target_index: str | None,
        replace: bool,
        preserve_raw: bool,
    ) -> dict[str, IndexOutcome | Exception]:
        return _IndexRun(
            self, payloads, resource, target_index, replace, preserve_raw
        ).execute()


class _IndexRun:
    """State of one ``StreamIndexer.index`` call."""

    def __init__(
        self,
        owner: StreamIndexer,
        payloads: dict[str, IndexPayload],
        resource: str,
        target_index: str | None,
        replace: bool,
        preserve_raw: bool,
    ) -> None:
        self._owner = owner
        self._payloads = payloads
        self._resource = resource
        self._target_index = target_index
        self._replace = replace
        self._preserve_raw = preserve_raw
        self._failed: dict[str, Exception] = {}
        self._indexed = dict.fromkeys(payloads, 0)
        self._batches = dict.fromkeys(payloads, 0)
        self._streams = {
            job_id: RedisRecordStream(owner.redis, payload.stream)
            for job_id, payload in payloads.items()
        }
        self._buffer: list[tuple[str, str, dict[str, object]]] = []

    def execute(self) -> dict[str, IndexOutcome | Exception]:
        consumer = f"worker-{os.getpid()}"
        for job_id, payload in self._payloads.items():
            self._drain(job_id, payload, consumer)
        self._flush()
        return {job_id: self._outcome(job_id) for job_id in self._payloads}

    def _drain(self, job_id: str, payload: IndexPayload, consumer: str) -> None:
        group = self._owner.group(payload)
        try:
            while job_id not in self._failed:
                entries = self._streams[job_id].read_batch(
                    group, count=payload.batch_size, consumer=consumer, block_ms=None
                )
                if not entries:
                    break
                for entry_id, entry in entries:
                    self._buffer.append((job_id, entry_id, self._document(entry)))
                if len(self._buffer) >= self._owner.batch_docs:
                    self._flush()
        except Exception as exc:  # noqa: BLE001 - attributed to this job.
            self._failed.setdefault(job_id, exc)

    def _document(self, entry: StreamEntry) -> dict[str, object]:
        document = to_document(
            entry.record,
            self._resource,
            preserve_raw=self._preserve_raw,
            ingest_metadata=entry.ingest_metadata,
        )
        validate_document(document, self._resource)
        return document

    def _flush(self) -> None:
        if not self._buffer:
            return
        owners = {job_id for job_id, _, _ in self._buffer}
        try:
            result = bulk_upsert(
                self._owner.client,
                self._resource,
                [document for _, _, document in self._buffer],
                target_index=self._target_index,
                replace=self._replace,
            )
            if result.get("errors"):
                raise RuntimeError(
                    "OpenSearch bulk indexing failed: "
                    f"{result.get('error_details', [])}"
                )
        except Exception as exc:  # noqa: BLE001 - attributed to the owning jobs.
            for job_id in owners:
                self._failed.setdefault(job_id, exc)
            self._buffer.clear()
            return
        acked: dict[str, list[str]] = {}
        for job_id, entry_id, _ in self._buffer:
            acked.setdefault(job_id, []).append(entry_id)
        for job_id, entry_ids in acked.items():
            group = self._owner.group(self._payloads[job_id])
            self._streams[job_id].acknowledge(group, entry_ids)
            self._indexed[job_id] += len(entry_ids)
            self._batches[job_id] += 1
        self._buffer.clear()

    def _outcome(self, job_id: str) -> IndexOutcome | Exception:
        if job_id in self._failed:
            return self._failed[job_id]
        payload = self._payloads[job_id]
        redis = self._owner.redis
        try:
            pending = cast(
                "dict[str, int]",
                redis.xpending(payload.stream, self._owner.group(payload)),
            )
            return IndexOutcome(
                stream=payload.stream,
                resource=self._resource,
                indexed=self._indexed[job_id],
                batches=self._batches[job_id],
                pending=int(pending["pending"]),
                stream_length=int(cast("int", redis.xlen(payload.stream))),
            )
        except Exception as exc:  # noqa: BLE001
            return exc

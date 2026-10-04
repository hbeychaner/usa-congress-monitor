"""Index several Redis streams through shared bulk requests."""

from __future__ import annotations

import os
from typing import Any

from cdm.ingest.redis_stream import RedisRecordStream
from cdm.store.indexer import to_document
from cdm.store.mapping_validation import validate_document
from cdm.store.opensearch import bulk_upsert


def index_streams(
    redis_client: Any,
    opensearch_client: Any,
    payloads: dict[str, dict[str, Any]],
    *,
    resource: str,
    target_index: str | None,
    replace: bool,
    preserve_raw: bool,
    batch_docs: int,
) -> dict[str, dict[str, Any] | Exception]:
    """Drain each job's stream, flushing one bulk per ``batch_docs`` documents.

    Streams are acknowledged only after their bulk succeeds. A failed bulk
    fails every job that contributed to it and leaves those entries pending
    for redelivery.
    """
    consumer = f"worker-{os.getpid()}"
    failed: dict[str, Exception] = {}
    indexed: dict[str, int] = dict.fromkeys(payloads, 0)
    batches: dict[str, int] = dict.fromkeys(payloads, 0)
    streams = {
        job_id: RedisRecordStream(redis_client, payload["stream"])
        for job_id, payload in payloads.items()
    }
    buffer: list[tuple[str, str, dict[str, Any]]] = []

    def flush() -> None:
        if not buffer:
            return
        owners = {job_id for job_id, _, _ in buffer}
        try:
            result = bulk_upsert(
                opensearch_client,
                resource,
                [document for _, _, document in buffer],
                target_index=target_index,
                replace=replace,
            )
            if result.get("errors"):
                raise RuntimeError(
                    "OpenSearch bulk indexing failed: "
                    f"{result.get('error_details', [])}"
                )
        except Exception as exc:  # noqa: BLE001 - attributed to the owning jobs.
            for job_id in owners:
                failed.setdefault(job_id, exc)
            buffer.clear()
            return
        acked: dict[str, list[str]] = {}
        for job_id, entry_id, _ in buffer:
            acked.setdefault(job_id, []).append(entry_id)
        for job_id, entry_ids in acked.items():
            group = payloads[job_id].get("consumer_group", "congress-indexers")
            streams[job_id].acknowledge(group, entry_ids)
            indexed[job_id] += len(entry_ids)
            batches[job_id] += 1
        buffer.clear()

    for job_id, payload in payloads.items():
        group = payload.get("consumer_group", "congress-indexers")
        count = int(payload.get("batch_size", 500))
        try:
            while job_id not in failed:
                entries = streams[job_id].read_batch(
                    group, count=count, consumer=consumer, block_ms=None
                )
                if not entries:
                    break
                for entry_id, entry in entries:
                    document = to_document(
                        entry["record"],
                        resource,
                        preserve_raw=preserve_raw,
                        ingest_metadata=entry.get("ingest_metadata"),
                    )
                    validate_document(document, resource)
                    buffer.append((job_id, entry_id, document))
                if len(buffer) >= batch_docs:
                    flush()
        except Exception as exc:  # noqa: BLE001 - attributed to this job.
            failed.setdefault(job_id, exc)
    flush()

    results: dict[str, dict[str, Any] | Exception] = {}
    for job_id, payload in payloads.items():
        if job_id in failed:
            results[job_id] = failed[job_id]
            continue
        group = payload.get("consumer_group", "congress-indexers")
        try:
            results[job_id] = {
                "stream": payload["stream"],
                "resource": resource,
                "indexed": indexed[job_id],
                "batches": batches[job_id],
                "pending": int(
                    redis_client.xpending(payload["stream"], group)["pending"]
                ),
                "stream_length": int(redis_client.xlen(payload["stream"])),
                "status": "completed",
            }
        except Exception as exc:  # noqa: BLE001
            results[job_id] = exc
    return results

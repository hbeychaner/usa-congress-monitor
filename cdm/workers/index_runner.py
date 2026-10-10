"""Runs index jobs: Redis stream -> bulk upsert, with archive replay fallback."""

from __future__ import annotations

import logging
from pathlib import Path

from elasticsearch import Elasticsearch
from redis import Redis

from cdm.config.app_config import IndexingConfig
from cdm.ingest.archive import JsonlRecordArchive
from cdm.jobs.payloads import IndexPayload
from cdm.jobs.store import JobKind, JobRow, JobStore
from cdm.store.batch_indexing import IndexOutcome, StreamIndexer
from cdm.store.index_manager import IndexManager
from cdm.store.indexer import to_document
from cdm.store.mapping_validation import validate_document
from cdm.store.opensearch import bulk_upsert, resource_target
from cdm.workers.results import JobResult, SkippedClaim

logger = logging.getLogger(__name__)


class ArchiveReplayer:
    """Bulk-upserts archived records for an index job whose stream is gone."""

    def __init__(self, client: Elasticsearch) -> None:
        self._client = client

    def replay(self, payload: IndexPayload) -> int:
        if (
            not payload.archive_root
            or not (Path(payload.archive_root) / "records.sqlite3").exists()
        ):
            return 0
        records = JsonlRecordArchive(Path(payload.archive_root), 0).records(
            payload.resource
        )
        replayed = 0
        for start in range(0, len(records), payload.batch_size):
            documents = [
                to_document(record, payload.resource, preserve_raw=payload.preserve_raw)
                for record in records[start : start + payload.batch_size]
            ]
            for document in documents:
                validate_document(document, payload.resource)
            result = bulk_upsert(
                self._client,
                payload.resource,
                documents,
                target_index=payload.target_index,
                replace=payload.replace,
            )
            if result.get("errors"):
                raise RuntimeError(
                    "OpenSearch bulk indexing failed during archive replay for "
                    f"{payload.archive_root}: {result.get('error_details', [])}"
                )
            replayed += len(documents)
        return replayed


class IndexJobRunner:
    def __init__(
        self,
        store: JobStore,
        redis_client: Redis,
        client: Elasticsearch,
        indexing: IndexingConfig,
        default_group: str,
    ) -> None:
        self._store = store
        self._client = client
        self._indexing = indexing
        self._indexer = StreamIndexer(
            redis_client,
            client,
            batch_docs=indexing.index_batch_docs,
            default_group=default_group,
        )
        self._replayer = ArchiveReplayer(client)

    def run(self, job_id: str) -> JobResult:
        job = self._store.mark_running(job_id)
        if job is None:
            return SkippedClaim(self._store).result(job_id)
        payload = IndexPayload.model_validate(job["payload"])
        claimed = self._claim_batch(job_id, payload)
        jobs = {job_id: payload} | {
            str(other["id"]): IndexPayload.model_validate(other["payload"])
            for other in claimed
        }
        try:
            outcomes = self._index(payload, jobs)
        except Exception as exc:
            for other in claimed:
                self._store.mark_failed(str(other["id"]), str(exc))
            raise
        return self._finalize(job_id, jobs, outcomes)

    def _claim_batch(self, job_id: str, payload: IndexPayload) -> list[JobRow]:
        extra = self._indexing.index_batch_jobs - 1
        if extra <= 0:
            return []
        return self._store.claim_queued(
            JobKind.INDEX.value,
            lambda other: payload.shares_batch_with(
                IndexPayload.model_validate(other["payload"])
            ),
            extra,
            exclude={job_id},
        )

    def _index(
        self, payload: IndexPayload, jobs: dict[str, IndexPayload]
    ) -> dict[str, IndexOutcome | Exception]:
        target, _ = resource_target(payload.resource)
        target_index = payload.target_index
        if target_index and not self._client.indices.exists(index=target_index):
            logger.warning(
                "Staging index %s is gone; indexing %s via its write alias",
                target_index,
                payload.resource,
            )
            target_index = None
        if not target_index:
            IndexManager(self._client).create(target, exists_ok=True)
        return self._indexer.index(
            jobs,
            resource=payload.resource,
            target_index=target_index,
            replace=payload.replace,
            preserve_raw=payload.preserve_raw,
        )

    def _finalize(
        self,
        job_id: str,
        jobs: dict[str, IndexPayload],
        outcomes: dict[str, IndexOutcome | Exception],
    ) -> JobResult:
        own_error: Exception | None = None
        own_result: IndexOutcome | None = None
        for current_id, outcome in outcomes.items():
            try:
                if isinstance(outcome, Exception):
                    raise outcome
                self._check_complete(jobs[current_id], outcome)
                self._store.mark_succeeded(current_id)
                if current_id == job_id:
                    own_result = outcome
            except Exception as exc:  # noqa: BLE001
                if current_id == job_id:
                    own_error = exc
                else:
                    self._store.mark_failed(current_id, str(exc))
        if own_error is not None:
            raise own_error
        fields = own_result.model_dump(exclude_none=True) if own_result else {}
        return JobResult(**fields, batched_jobs=len(jobs))

    def _check_complete(self, payload: IndexPayload, outcome: IndexOutcome) -> None:
        if outcome.pending != 0:
            raise RuntimeError(
                f"Redis stream still has {outcome.pending} pending entries: "
                f"{payload.stream}"
            )
        expected = payload.expected_count
        if expected is not None and outcome.indexed < expected:
            # The stream may have been trimmed or lost (Redis restart, maxlen
            # eviction); the durable per-job archive is the fallback source.
            replayed = self._replayer.replay(payload)
            outcome.replayed_from_archive = replayed
            if outcome.indexed + replayed < expected:
                raise RuntimeError(
                    f"Indexed {outcome.indexed} records "
                    f"(+{replayed} archive replays), expected at least "
                    f"{expected}: {payload.stream}"
                )

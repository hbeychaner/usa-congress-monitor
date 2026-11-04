import multiprocessing
import os
import signal
import sqlite3
import time
from collections.abc import Iterator, Sequence
from contextlib import ExitStack, closing
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Literal
from unittest.mock import Mock
from uuid import uuid4

import pytest
from celery import Celery
from elasticsearch import Elasticsearch
from pydantic import BaseModel, TypeAdapter
from redis import Redis
from redis.typing import StreamIdT
from sqlalchemy import select, update

from cdm.config.app_config import IndexingConfig, QueueConfig
from cdm.ingest.archive import SQLiteRecordArchive
from cdm.ingest.redis_stream import RedisRecordStream
from cdm.jobs.payloads import IndexPayload
from cdm.jobs.store import _JOBS, JobKind, JobStatus, JobStore
from cdm.store.batch_indexing import IndexOutcome, StreamIndexer
from cdm.store.index_manager import load_definitions
from cdm.store.indexer import to_document
from cdm.workers.dispatch import JobDispatcher, TaskName
from cdm.workers.failures import FailureClassifier
from cdm.workers.index_runner import IndexJobRunner
from cdm.workers.maintenance import ActiveJobProbe, JobRecoveryService, QueueDepthProbe
from cdm.workers.results import RetryableTask, TaskRetrier


class HandoffFailure(StrEnum):
    ARCHIVE_ONLY = "archive_only"
    TRIMMED_PENDING = "trimmed_pending"
    LOST_STREAM = "lost_stream"


class HandoffRoute(StrEnum):
    STREAM = "stream"
    ARCHIVE = "archive"


class HandoffMeasurement(BaseModel):
    route: HandoffRoute
    records: int
    seconds: float
    stream_bytes: int
    stream_entries: int


class PipelineConfig(BaseModel):
    resource: Literal["bill"] = "bill"
    group: str = "acceptance"
    abandoned_consumer: str = "abandoned"
    reclaim_idle_ms: int = 61_000
    batch_docs: int = 2


class SyntheticBill(BaseModel):
    id: str
    number: str
    title: str
    congress: int = 119
    type: Literal["hr"] = "hr"


class PendingSummary(BaseModel):
    pending: int


class CrashCheckpoint(BaseModel):
    stage: Literal["archived"] = "archived"
    progress: float = 0.5


class InterruptedWriter(BaseModel):
    ledger: Path
    archive: Path
    job_id: str
    bills: list[SyntheticBill]

    def run(self, ready: Connection) -> None:
        store = JobStore(self.ledger, repair=False)
        archive = SQLiteRecordArchive(self.archive, 0)
        try:
            with store.engine.connect() as keeper:
                keeper.execute(select(_JOBS.c.id).limit(1)).first()
                assert store.mark_running(self.job_id) is not None
                for bill in self.bills:
                    archive.write("bill", bill.model_dump(mode="json"))
                store.report_progress(
                    self.job_id, CrashCheckpoint().model_dump(mode="json")
                )
                ready.send(True)
                ready.recv()
        finally:
            ready.close()
            archive.engine.dispose()
            store.engine.dispose()


class SQLiteSnapshot(BaseModel):
    ledger: Path
    archive: Path

    @staticmethod
    def copy_database(source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        with (
            closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as live,
            closing(sqlite3.connect(target)) as copied,
        ):
            live.backup(copied)
            assert copied.execute("PRAGMA integrity_check").fetchone() == ("ok",)


class PipelineFixture:
    def __init__(
        self,
        client: Elasticsearch,
        redis: Redis,
        store: JobStore,
        archive: SQLiteRecordArchive,
        index: str,
        config: PipelineConfig,
    ) -> None:
        self.client = client
        self.redis = redis
        self.store = store
        self.archive = archive
        self.index = index
        self.config = config
        self.streams: set[str] = set()
        self.bills = [
            SyntheticBill(
                id=f"bill:119:hr:{number}",
                number=str(number),
                title=f"Acceptance bill {number}",
            )
            for number in (1, 2)
        ]

    def stream(self, name: str) -> RedisRecordStream:
        key = f"{self.index}:{name}"
        self.streams.add(key)
        return RedisRecordStream(self.redis, key)

    def cleanup_streams(self) -> None:
        if self.streams:
            self.redis.delete(*self.streams)

    def archive_bills(self, bills: list[SyntheticBill]) -> None:
        for bill in bills:
            self.archive.write(self.config.resource, bill.model_dump(mode="json"))
        self.archive.engine.dispose()

    def publish(self, stream: RedisRecordStream, bill: SyntheticBill) -> str:
        return stream.publish(self.config.resource, bill.model_dump(mode="json"))

    def pending(self, stream: RedisRecordStream) -> int:
        return PendingSummary.model_validate(
            self.redis.xpending(stream.stream, self.config.group)
        ).pending

    def age(self, stream: RedisRecordStream, entry_ids: Sequence[StreamIdT]) -> None:
        self.redis.xclaim(
            stream.stream,
            self.config.group,
            self.config.abandoned_consumer,
            min_idle_time=0,
            message_ids=list(entry_ids),
            idle=self.config.reclaim_idle_ms,
        )

    def payload(self, stream: RedisRecordStream, expected: int) -> IndexPayload:
        return IndexPayload(
            stream=stream.stream,
            resource=self.config.resource,
            batch_size=self.config.batch_docs,
            consumer_group=self.config.group,
            expected_count=expected,
            archive_root=str(self.archive.root),
            target_index=self.index,
            replace=True,
        )

    def drain(
        self, payloads: dict[str, IndexPayload]
    ) -> dict[str, IndexOutcome | Exception]:
        return StreamIndexer(
            self.redis,
            self.client,
            batch_docs=self.config.batch_docs,
            default_group=self.config.group,
        ).index(
            payloads,
            resource=self.config.resource,
            target_index=self.index,
            replace=True,
            preserve_raw=False,
        )

    def runner(self) -> IndexJobRunner:
        return IndexJobRunner(
            self.store,
            self.redis,
            self.client,
            IndexingConfig(index_batch_docs=self.config.batch_docs),
            self.config.group,
        )

    def assert_preserved(self) -> None:
        self.client.indices.refresh(index=self.index)
        assert self.client.count(index=self.index)["count"] == len(self.bills)
        for bill in self.bills:
            source = self.client.get(index=self.index, id=bill.id)["_source"]
            assert source["title"] == bill.title
        archived = [
            SyntheticBill.model_validate(record)
            for record in self.archive.records(self.config.resource)
        ]
        assert sorted(archived, key=lambda bill: bill.id) == sorted(
            self.bills, key=lambda bill: bill.id
        )


@pytest.fixture
def pipeline(tmp_path: Path) -> Iterator[PipelineFixture]:
    search_url = os.environ.get("PIPELINE_TEST_SEARCH_URL")
    redis_url = os.environ.get("PIPELINE_TEST_REDIS_URL")
    if not search_url or not redis_url:
        pytest.skip(
            "Set PIPELINE_TEST_SEARCH_URL and PIPELINE_TEST_REDIS_URL "
            "to isolated synthetic test services"
        )
    with ExitStack() as cleanup:
        client = Elasticsearch(
            search_url,
            api_key=os.environ.get("PIPELINE_TEST_SEARCH_API_KEY"),
            request_timeout=30,
        )
        cleanup.callback(client.close)
        redis = Redis.from_url(redis_url, decode_responses=True)
        cleanup.callback(redis.close)
        store = JobStore(tmp_path / "jobs.sqlite3", repair=False)
        cleanup.callback(store.engine.dispose)
        archive = SQLiteRecordArchive(tmp_path / "archive", 0)
        cleanup.callback(archive.engine.dispose)
        index = f"pipeline-acceptance-{uuid4().hex}"
        client.indices.create(index=index, **load_definitions()["legislation"])
        cleanup.callback(
            client.options(ignore_status=404).ingest.delete_pipeline, id=index
        )
        cleanup.callback(client.indices.delete, index=index, ignore_unavailable=True)
        fixture = PipelineFixture(
            client, redis, store, archive, index, PipelineConfig()
        )
        cleanup.callback(fixture.cleanup_streams)
        yield fixture


class TestPipelineFailures:
    @pytest.mark.parametrize("route", list(HandoffRoute))
    def test_bounded_handoff_comparison(
        self, pipeline: PipelineFixture, route: HandoffRoute
    ) -> None:
        pipeline.config.batch_docs = 25
        pipeline.bills = [
            SyntheticBill(
                id=f"bill:119:hr:{number}",
                number=str(number),
                title=f"Transport comparison bill {number}",
            )
            for number in range(1, 101)
        ]
        stream = pipeline.stream("comparison")
        to_document(pipeline.bills[0].model_dump(mode="json"), pipeline.config.resource)
        started = time.perf_counter()
        pipeline.archive_bills(pipeline.bills)
        if route == HandoffRoute.STREAM:
            for bill in pipeline.bills:
                pipeline.publish(stream, bill)
        job = pipeline.store.create(
            JobKind.INDEX, "comparison", pipeline.payload(stream, 100).to_json()
        )
        result = pipeline.runner().run(job["id"])
        elapsed = time.perf_counter() - started
        assert pipeline.store.get(job["id"])["status"] == JobStatus.SUCCEEDED
        assert result.model_dump()["indexed"] == (
            100 if route == HandoffRoute.STREAM else 0
        )
        assert result.model_dump().get("replayed_from_archive") == (
            100 if route == HandoffRoute.ARCHIVE else None
        )
        pipeline.assert_preserved()
        measurement = HandoffMeasurement(
            route=route,
            records=100,
            seconds=elapsed,
            stream_bytes=TypeAdapter(int).validate_python(
                pipeline.redis.memory_usage(stream.stream)
            ),
            stream_entries=TypeAdapter(int).validate_python(
                pipeline.redis.xlen(stream.stream)
            ),
        )
        assert measurement.stream_entries == (
            100 if route == HandoffRoute.STREAM else 0
        )
        print(measurement.model_dump_json())

    def test_killed_writer_restores_from_wal_backup_and_replays_archive(
        self, pipeline: PipelineFixture, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        stream = pipeline.stream("crash-restore")
        payload = pipeline.payload(stream, 2)
        job = pipeline.store.create(JobKind.INDEX, "crash-restore", payload.to_json())
        terminal = pipeline.store.create(
            JobKind.INDEX, "already-done", payload.to_json()
        )
        pipeline.store.mark_running(terminal["id"])
        completed = pipeline.store.mark_succeeded(terminal["id"])
        snapshot_root = tmp_path_factory.mktemp("recovery-snapshot")
        snapshot = SQLiteSnapshot(
            ledger=snapshot_root / "jobs.sqlite3",
            archive=snapshot_root / "records.sqlite3",
        )
        context = multiprocessing.get_context("spawn")
        ready, sender = context.Pipe()
        process = context.Process(
            target=InterruptedWriter(
                ledger=pipeline.store.path,
                archive=pipeline.archive.root,
                job_id=job["id"],
                bills=pipeline.bills,
            ).run,
            args=(sender,),
        )
        process.start()
        try:
            assert ready.poll(60), "Writer did not reach its committed checkpoint"
            assert ready.recv() is True and process.is_alive()
            assert pipeline.store.path.with_name("jobs.sqlite3-wal").stat().st_size > 0
            snapshot.copy_database(pipeline.store.path, snapshot.ledger)
            snapshot.copy_database(pipeline.archive.path, snapshot.archive)
            process.kill()
            process.join(10)
            assert process.exitcode == -signal.SIGKILL
        finally:
            if process.is_alive():
                process.kill()
            process.join(10)
            ready.close()
            sender.close()
            process.close()

        assert pipeline.store.get(job["id"])["status"] == JobStatus.RUNNING
        assert pipeline.store.progress(job["id"]) == CrashCheckpoint().model_dump(
            mode="json"
        )
        late_bill = SyntheticBill(
            id="bill:119:hr:3", number="3", title="After the snapshot"
        )
        pipeline.archive.write("bill", late_bill.model_dump(mode="json"))
        pipeline.store.create(JobKind.INDEX, "after-snapshot", payload.to_json())
        pipeline.archive.engine.dispose()
        pipeline.store.engine.dispose()
        live_root = pipeline.store.path.parent
        preserved = live_root.with_name(f"{live_root.name}-pre-restore-{uuid4().hex}")
        live_root.rename(preserved)
        snapshot.copy_database(snapshot.ledger, pipeline.store.path)
        snapshot.copy_database(snapshot.archive, pipeline.archive.path)

        with ExitStack() as cleanup:
            restored = JobStore(pipeline.store.path, repair=False)
            cleanup.callback(restored.engine.dispose)
            original = JobStore(preserved / "jobs.sqlite3", repair=False)
            cleanup.callback(original.engine.dispose)
            original_archive = SQLiteRecordArchive(preserved / "archive", 0)
            cleanup.callback(original_archive.engine.dispose)
            assert original.get("after-snapshot")["status"] == JobStatus.QUEUED
            assert late_bill.id in original_archive.ids("bill")
            with pytest.raises(KeyError, match="after-snapshot"):
                restored.get("after-snapshot")
            assert restored.get(terminal["id"]) == completed
            assert restored.progress(job["id"]) == CrashCheckpoint().model_dump(
                mode="json"
            )
            with restored.engine.begin() as connection:
                connection.execute(
                    update(_JOBS)
                    .where(_JOBS.c.id == job["id"])
                    .values(
                        updated_at=(
                            datetime.now(UTC)
                            - JobRecoveryService.CRASH_CUTOFF
                            - timedelta(seconds=1)
                        ).isoformat()
                    )
                )
            app = Mock(spec=Celery)
            queues = QueueConfig.model_construct()
            depth = Mock(spec=QueueDepthProbe)
            depth.depth.return_value = 0
            active = Mock(spec=ActiveJobProbe)
            active.job_ids.return_value = set()
            recovered = JobRecoveryService(
                restored,
                pipeline.redis,
                JobDispatcher(app, queues),
                depth,
                FailureClassifier(),
                queues,
                active,
            ).recover()
            assert recovered.recovered == [job["id"]]
            app.send_task.assert_called_once_with(
                TaskName.RUN_INDEX, args=[job["id"]], queue=queues.celery_index_queue
            )
            runner = IndexJobRunner(
                restored,
                pipeline.redis,
                pipeline.client,
                IndexingConfig(index_batch_docs=pipeline.config.batch_docs),
                pipeline.config.group,
            )
            result = IndexOutcome.model_validate(runner.run(job["id"]).model_dump())
            assert result.indexed == 0 and result.replayed_from_archive == 2
            assert result.pending == 0
            assert restored.get(job["id"])["status"] == JobStatus.SUCCEEDED
            assert restored.get(job["id"])["attempts"] == 2
            assert runner.run(job["id"]).skipped is True
            assert restored.get(terminal["id"]) == completed
            pipeline.assert_preserved()

    def test_partial_bulk_reclaims_every_owner_without_duplicate_documents(
        self, pipeline: PipelineFixture
    ) -> None:
        pipeline.archive_bills(pipeline.bills)
        first, second = pipeline.stream("first"), pipeline.stream("second")
        first_id = pipeline.publish(first, pipeline.bills[0])
        second_id = pipeline.publish(second, pipeline.bills[1])
        payloads = {
            first.stream: pipeline.payload(first, 1),
            second.stream: pipeline.payload(second, 1),
        }
        pipeline.client.ingest.put_pipeline(
            id=pipeline.index,
            processors=[
                {
                    "fail": {
                        "if": "ctx.id == 'bill:119:hr:2'",
                        "message": "controlled acceptance rejection",
                    }
                }
            ],
        )
        pipeline.client.indices.put_settings(
            index=pipeline.index,
            settings={"index.default_pipeline": pipeline.index},
        )

        failed = pipeline.drain(payloads)

        assert failed.keys() == payloads.keys()
        assert all(isinstance(outcome, RuntimeError) for outcome in failed.values())
        assert all(
            "controlled acceptance rejection" in str(outcome)
            for outcome in failed.values()
        )
        assert all(pipeline.bills[1].id in str(outcome) for outcome in failed.values())
        classifier = FailureClassifier()
        for outcome in failed.values():
            assert isinstance(outcome, RuntimeError)
            assert not classifier.is_transient(outcome)
            assert not classifier.is_retryable_error(str(outcome))
        assert pipeline.client.exists(index=pipeline.index, id=pipeline.bills[0].id)
        assert not pipeline.client.exists(index=pipeline.index, id=pipeline.bills[1].id)
        assert pipeline.pending(first) == pipeline.pending(second) == 1
        assert len(pipeline.archive.records(pipeline.config.resource)) == 2

        pipeline.client.indices.put_settings(
            index=pipeline.index, settings={"index.default_pipeline": "_none"}
        )
        pipeline.age(first, [first_id])
        pipeline.age(second, [second_id])
        recovered = pipeline.drain(payloads)

        assert recovered.keys() == payloads.keys()
        for outcome in recovered.values():
            assert isinstance(outcome, IndexOutcome)
            assert outcome.indexed == 1
            assert outcome.pending == 0
        pipeline.assert_preserved()

        repeated = pipeline.drain(payloads)
        assert repeated.keys() == payloads.keys()
        for outcome in repeated.values():
            assert isinstance(outcome, IndexOutcome)
            assert outcome.indexed == 0
            assert outcome.pending == 0
        pipeline.assert_preserved()

    def test_permanent_rejection_is_persisted_for_every_batched_owner(
        self, pipeline: PipelineFixture
    ) -> None:
        pipeline.archive_bills(pipeline.bills)
        jobs: list[str] = []
        streams: list[RedisRecordStream] = []
        for number, bill in enumerate(pipeline.bills):
            stream = pipeline.stream(f"owner-{number}")
            streams.append(stream)
            pipeline.publish(stream, bill)
            jobs.append(
                pipeline.store.create(
                    JobKind.INDEX,
                    f"owner-{number}",
                    pipeline.payload(stream, 1).to_json(),
                )["id"]
            )
        pipeline.client.ingest.put_pipeline(
            id=pipeline.index,
            processors=[{"fail": {"message": "permanent acceptance rejection"}}],
        )
        pipeline.client.indices.put_settings(
            index=pipeline.index, settings={"index.default_pipeline": pipeline.index}
        )
        task = Mock(spec=RetryableTask)
        with pytest.raises(RuntimeError, match="Bulk indexing failed"):
            try:
                pipeline.runner().run(jobs[0])
            except RuntimeError as exc:
                TaskRetrier(pipeline.store, QueueConfig(), FailureClassifier()).handle(
                    task, jobs[0], exc
                )
        task.retry.assert_not_called()
        for job_id in jobs:
            row = pipeline.store.get(job_id)
            assert row["status"] == JobStatus.FAILED
            assert row["last_error"] is not None
            assert all(bill.id in row["last_error"] for bill in pipeline.bills)
            assert not FailureClassifier().is_retryable_error(row["last_error"])
        assert all(pipeline.pending(stream) == 1 for stream in streams)
        assert len(pipeline.archive.records(pipeline.config.resource)) == 2

    @pytest.mark.parametrize("failure", list(HandoffFailure))
    def test_archive_recovers_interrupted_handoff_and_terminal_delivery_skips(
        self, pipeline: PipelineFixture, failure: HandoffFailure
    ) -> None:
        pipeline.archive_bills(pipeline.bills)
        stream = pipeline.stream("handoff")
        if failure != HandoffFailure.ARCHIVE_ONLY:
            entry_ids = [pipeline.publish(stream, bill) for bill in pipeline.bills]
            if failure == HandoffFailure.TRIMMED_PENDING:
                entries = stream.read_batch(
                    pipeline.config.group,
                    count=2,
                    consumer=pipeline.config.abandoned_consumer,
                    block_ms=None,
                )
                assert [entry_id for entry_id, _ in entries] == entry_ids
                pipeline.age(stream, entry_ids)
                pipeline.redis.xtrim(stream.stream, maxlen=0, approximate=False)
                assert pipeline.pending(stream) == 2
            else:
                pipeline.redis.delete(stream.stream)
        job = pipeline.store.create(
            JobKind.INDEX, "handoff", pipeline.payload(stream, 2).to_json()
        )

        result = pipeline.runner().run(job["id"])

        outcome = IndexOutcome.model_validate(result.model_dump())
        assert outcome.indexed == 0
        assert outcome.replayed_from_archive == 2
        assert outcome.pending == 0
        finished = pipeline.store.get(job["id"])
        assert finished is not None
        assert finished["status"] == JobStatus.SUCCEEDED
        assert pipeline.pending(stream) == 0
        pipeline.assert_preserved()

        repeated = pipeline.runner().run(job["id"])
        assert repeated.skipped is True
        assert repeated.status == JobStatus.SUCCEEDED
        assert pipeline.store.get(job["id"]) == finished
        pipeline.assert_preserved()

    @pytest.mark.parametrize("overlapping_stream", [False, True])
    def test_incomplete_archive_cannot_report_success(
        self, pipeline: PipelineFixture, overlapping_stream: bool
    ) -> None:
        pipeline.archive_bills(pipeline.bills[:1])
        stream = pipeline.stream("incomplete")
        if overlapping_stream:
            pipeline.publish(stream, pipeline.bills[0])
        job = pipeline.store.create(
            JobKind.INDEX, "incomplete", pipeline.payload(stream, 2).to_json()
        )

        with pytest.raises(RuntimeError, match="expected at least 2"):
            pipeline.runner().run(job["id"])

        unfinished = pipeline.store.get(job["id"])
        assert unfinished is not None
        assert unfinished["status"] != JobStatus.SUCCEEDED
        assert len(pipeline.archive.records(pipeline.config.resource)) == 1

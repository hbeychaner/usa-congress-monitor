from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from elasticsearch import Elasticsearch
from redis import Redis

from cdm.config.app_config import IndexingConfig
from cdm.ingest.redis_stream import StreamEntry
from cdm.jobs.payloads import IndexPayload
from cdm.jobs.store import JobKind, JobStore
from cdm.store.batch_indexing import IndexOutcome, StreamIndexer
from cdm.workers.index_runner import IndexJobRunner


class TestIndexDestinations:
    @pytest.mark.parametrize("target", ["congress-legislation-staging", "", "  "])
    def test_missing_explicit_target_fails_before_consuming_stream(
        self, tmp_path: Path, target: str
    ) -> None:
        store = JobStore(tmp_path / "jobs.sqlite3", repair=False)
        payload = IndexPayload(
            stream="source-stream",
            resource="bill",
            target_index=target,
        )
        first = store.create(JobKind.INDEX, "first", payload.to_json())
        second = store.create(JobKind.INDEX, "second", payload.to_json())
        unrelated = store.create(
            JobKind.INDEX,
            "unrelated",
            payload.model_copy(update={"target_index": "other-staging"}).to_json(),
        )
        client = Mock(spec=Elasticsearch, indices=Mock())
        client.indices.exists.return_value = False
        redis = Mock(spec=Redis)
        runner = IndexJobRunner(
            store, redis, client, IndexingConfig(), default_group="indexers"
        )

        with pytest.raises(ValueError, match="Explicit index target"):
            runner.run(first["id"])

        redis.assert_not_called()
        assert not redis.method_calls
        client.indices.create.assert_not_called()
        failed = store.get(second["id"])
        assert failed is not None
        assert failed["status"] == "failed"
        assert failed["last_error"] is not None
        assert "Explicit index target" in failed["last_error"]
        queued = store.get(unrelated["id"])
        assert queued is not None
        assert queued["status"] == "queued"

    @pytest.mark.parametrize("target", [None, "congress-legislation-staging"])
    def test_existing_destination_is_forwarded_unchanged(
        self, tmp_path: Path, target: str | None
    ) -> None:
        store = JobStore(tmp_path / "jobs.sqlite3", repair=False)
        payload = IndexPayload(
            stream="source-stream", resource="bill", target_index=target
        )
        job = store.create(JobKind.INDEX, "first", payload.to_json())
        client = Mock(spec=Elasticsearch, indices=Mock())
        client.indices.exists.return_value = True
        runner = IndexJobRunner(
            store, Mock(spec=Redis), client, IndexingConfig(), default_group="indexers"
        )
        outcome = IndexOutcome(
            stream=payload.stream,
            resource=payload.resource,
            indexed=1,
            batches=1,
            pending=0,
            stream_length=1,
        )
        with (
            patch.object(
                runner._indexer, "index", return_value={job["id"]: outcome}
            ) as index,
            patch("cdm.workers.index_runner.IndexManager") as manager,
        ):
            result = runner.run(job["id"])

        assert result.model_dump()["indexed"] == 1
        assert index.call_args.kwargs["target_index"] == target
        if target is None:
            manager.return_value.create.assert_called_once_with(
                "legislation", exists_ok=True
            )
        else:
            manager.assert_not_called()


class TestStreamFailures:
    @pytest.mark.parametrize("destination_exists", [False, True])
    def test_failed_write_leaves_the_entire_batch_unacknowledged(
        self, destination_exists: bool
    ) -> None:
        client = Mock(spec=Elasticsearch, indices=Mock())
        client.indices.exists.return_value = destination_exists
        redis = Mock(spec=Redis)
        indexer = StreamIndexer(redis, client, batch_docs=2, default_group="indexers")
        entries = [
            (
                f"{number}-0",
                StreamEntry(resource="bill", record={"id": f"bill:118:hr:{number}"}),
            )
            for number in (1, 2)
        ]
        payload = IndexPayload(
            stream="source-stream",
            resource="bill",
            target_index="congress-legislation-staging",
        )
        with (
            patch(
                "cdm.store.batch_indexing.RedisRecordStream.read_batch",
                side_effect=[entries, []],
            ),
            patch(
                "cdm.store.opensearch.bulk",
                return_value=(1, [{"update": {"status": 400}}]),
            ) as bulk,
        ):
            outcomes = indexer.index(
                {"job": payload},
                resource=payload.resource,
                target_index=payload.target_index,
                replace=False,
                preserve_raw=False,
            )

        assert isinstance(
            outcomes["job"], RuntimeError if destination_exists else ValueError
        )
        redis.xack.assert_not_called()
        if destination_exists:
            bulk.assert_called_once()
        else:
            bulk.assert_not_called()


class TestReplayCompleteness:
    @pytest.mark.parametrize("replayed", [0, 1, 2])
    def test_archive_replay_is_a_complete_snapshot_not_additive_progress(
        self, tmp_path: Path, replayed: int
    ) -> None:
        store = JobStore(tmp_path / "jobs.sqlite3", repair=False)
        runner = IndexJobRunner(
            store,
            Mock(spec=Redis),
            Mock(spec=Elasticsearch),
            IndexingConfig(),
            default_group="indexers",
        )
        payload = IndexPayload(stream="overlapping", resource="bill", expected_count=2)
        outcome = IndexOutcome(
            stream=payload.stream,
            resource=payload.resource,
            indexed=1,
            batches=1,
            pending=0,
            stream_length=1,
        )
        with patch.object(runner._replayer, "replay", return_value=replayed):
            if replayed < 2:
                with pytest.raises(RuntimeError, match="expected at least 2"):
                    runner._check_complete(payload, outcome)
            else:
                runner._check_complete(payload, outcome)
        assert outcome.replayed_from_archive == replayed

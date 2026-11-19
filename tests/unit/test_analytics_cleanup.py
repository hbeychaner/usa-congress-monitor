from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import pytest
import requests
from elastic_transport import ObjectApiResponse
from elasticsearch import Elasticsearch

from cdm.config.app_config import AnalyticsRetentionConfig
from cdm.config.topic_analysis import EmbeddingCache
from cdm.graph.models import GraphPointerSnapshot, GraphVersionPointer, Signal
from cdm.graph.store import GraphStore
from cdm.jobs.store import JobKind, JobSlotsBusy, JobStore
from cdm.store.perspective_repository import (
    PerspectivePublication,
    PerspectiveRepository,
    PerspectiveSnapshot,
)
from cdm.store.topic_publication import (
    CompletedTopicRun,
    TopicPublicationPointer,
    TopicPublicationSnapshot,
    TopicPublicationStore,
    TopicRunCounts,
)
from cdm.topics.cleanup import AnalyticsCleanup, CleanupPolicy, CleanupRequest
from cdm.topics.retirement import RetirementReporter


class CleanupHarness:
    versions = ("20260101T000000Z", "20260102T000000Z", "20260103T000000Z")

    def __init__(self, root: Path) -> None:
        self.root = root
        self.cache = "embeddings-" + "a" * 64
        self.client = Mock(spec=Elasticsearch, indices=Mock())
        self.client.options.return_value = self.client
        self.client.search.side_effect = self.search
        self.client.delete_by_query.return_value = ObjectApiResponse(
            {"deleted": 7, "timed_out": False, "failures": [], "version_conflicts": 0},
            Mock(),
        )
        definitions = {
            index: {"aliases": {}, "settings": {"index": {"uuid": index}}}
            for index in ("embeddings", self.cache)
        }
        self.client.indices.get.side_effect = lambda *, index: {
            key: value
            for key, value in definitions.items()
            if index == "embeddings*" or key == index
        }
        self.client.indices.delete.return_value = {"acknowledged": True}
        runs = []
        for version in self.versions:
            directory = root / version
            directory.mkdir()
            for name in CleanupPolicy.artifact_files:
                (directory / name).write_bytes(b"data")
            runs.append(
                CompletedTopicRun(
                    model_version=version,
                    trained_at=datetime.now(UTC),
                    completed_at=datetime.now(UTC),
                    embedding_model="model",
                    embedding_cache=EmbeddingCache(
                        index=self.cache, model="model", dimensions=2
                    ),
                    min_congress=113,
                    corpus_size=1,
                    dated_documents=0,
                    model_path=str(directory),
                    counts=TopicRunCounts(
                        topics=1,
                        assignments=1,
                        over_time=0,
                        metasubjects=1,
                        metasubject_over_time=0,
                    ),
                )
            )
        topics = Mock(spec=TopicPublicationStore, index="topics")
        topics.snapshot.return_value = TopicPublicationSnapshot(
            pointer=TopicPublicationPointer(run=runs[2], previous=runs[1]),
            seq_no=1,
            primary_term=1,
        )
        graphs = Mock(spec=GraphStore, index="graphs")
        graphs.pointer_snapshot.side_effect = lambda signal: GraphPointerSnapshot(
            signal=signal,
            sequence_number=1,
            primary_term=1,
            pointer=GraphVersionPointer(
                signal=signal,
                graph_version=self.versions[2],
                built_at=datetime(2026, 1, 3, tzinfo=UTC),
                source_model_version=self.versions[2]
                if signal == Signal.TOPIC
                else None,
                previous=GraphVersionPointer(
                    signal=signal,
                    graph_version=self.versions[1],
                    built_at=datetime(2026, 1, 2, tzinfo=UTC),
                    source_model_version=self.versions[1]
                    if signal == Signal.TOPIC
                    else None,
                ),
            ),
        )
        perspectives = Mock(spec=PerspectiveRepository)
        perspectives.congresses.return_value = [119]
        perspectives.snapshot.return_value = PerspectiveSnapshot(
            congress=119,
            sequence_number=1,
            primary_term=1,
            publication=PerspectivePublication(
                congress=119,
                model_version=self.versions[2],
                built_at=datetime.now(UTC),
                results=[],
                previous=PerspectivePublication(
                    congress=119,
                    model_version=self.versions[1],
                    built_at=datetime.now(UTC),
                    results=[],
                ),
            ),
        )
        reporter = Mock(spec=RetirementReporter)
        reporter.report.return_value = Mock(
            warnings=[],
            references=[],
            unknown_cache_versions=[],
            runs=[Mock(run=run) for run in runs],
        )
        self.store = JobStore(root.parent / "jobs.sqlite3", repair=False)
        http = Mock(spec=requests.Session)
        http.get.side_effect = lambda url, **_kwargs: self.http(httpx.Request("GET", url))
        self.service = AnalyticsCleanup(
            self.client,
            topics,
            graphs,
            perspectives,
            reporter,
            self.store,
            http,
            AnalyticsRetentionConfig(analytics_model_root=root),
            "embeddings",
        )

    def search(self, **_kwargs: object) -> ObjectApiResponse:
        return ObjectApiResponse(
            {
                "timed_out": False,
                "_shards": {"failed": 0},
                "aggregations": {
                    "versions": {
                        "sum_other_doc_count": 0,
                        "doc_count_error_upper_bound": 0,
                        "buckets": [
                            {"key": version, "doc_count": 7}
                            for version in self.versions
                        ],
                    }
                },
                "hits": {"hits": [{"_source": {"member": "A"}}]},
            },
            Mock(),
        )

    def http(self, request: httpx.Request) -> httpx.Response:
        version = self.versions[2]
        analysis = {
            "state": "available",
            "source_model_version": version,
            "published_model_version": version,
        }
        if request.url.path.endswith("/topics"):
            return httpx.Response(
                200,
                request=request,
                json={
                    "model_version": version,
                    "analysis": analysis,
                    "topics": [{"topic_id": 1, "name": "a", "label": "a", "size": 1}],
                },
            )
        if request.url.path.endswith("/parties"):
            return httpx.Response(
                200,
                request=request,
                json={
                    "model_version": version,
                    "analysis": analysis,
                    "congress": 119,
                    "congresses": [119],
                    "parties": [],
                    "bilateral": [],
                },
            )
        return httpx.Response(
            200,
            request=request,
            json={
                "seeds": ["A"],
                "analysis": {signal: analysis for signal in Signal},
                "versions": {signal: version for signal in Signal},
            },
        )


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[CleanupHarness]:
    root = tmp_path / "topics"
    root.mkdir()
    harness = CleanupHarness(root)
    yield harness
    harness.service._http.close()
    harness.store.engine.dispose()


def test_plan_and_cleanup_keep_exactly_current_previous_and_shared_cache(
    harness: CleanupHarness,
) -> None:
    plan = harness.service.plan()
    assert plan.retained_models == set(harness.versions[1:])
    assert plan.directories == [harness.root / harness.versions[0]]
    assert set(plan.caches) == {"embeddings"}
    assert len(plan.generations) == 5
    harness.client.delete_by_query.assert_not_called()
    harness.client.indices.delete.assert_not_called()

    result = harness.service.apply(plan)

    assert result.documents_deleted == 35
    assert result.model_bytes_freed == 20
    assert result.directories_deleted == 1
    assert result.caches_deleted == ["embeddings"]
    assert all((harness.root / version).is_dir() for version in harness.versions[1:])
    assert not (harness.root / harness.versions[0]).exists()
    for call in harness.client.delete_by_query.call_args_list:
        assert call.kwargs["conflicts"] == "abort"
        assert call.kwargs["scroll_size"] == 500
        assert harness.versions[0] in str(call.kwargs["query"])


@pytest.mark.parametrize("unsafe", ["extra-file", "symlink"])
def test_unknown_artifacts_block_cleanup_before_any_deletion(
    harness: CleanupHarness, unsafe: str
) -> None:
    directory = harness.root / harness.versions[0]
    if unsafe == "extra-file":
        (directory / "important.txt").write_text("keep")
    else:
        path = directory / "topics.json"
        path.unlink()
        path.symlink_to(harness.root / harness.versions[2] / "topics.json")
    with pytest.raises(ValueError, match="Unrecognized files"):
        harness.service.plan()
    harness.client.delete_by_query.assert_not_called()
    harness.client.indices.delete.assert_not_called()


def test_wrong_live_generation_refuses_all_deletion(harness: CleanupHarness) -> None:
    plan = harness.service.plan()
    with (
        patch.object(
            harness.service._http,
            "get",
            return_value=httpx.Response(
                200,
                request=httpx.Request("GET", "http://test/topics"),
                json={
                    "topics": [],
                    "model_version": harness.versions[1],
                    "analysis": {
                        "state": "stale",
                        "source_model_version": harness.versions[1],
                    },
                },
            ),
        ),
        pytest.raises(ValueError, match="Live topics"),
    ):
        harness.service.apply(plan)
    harness.client.delete_by_query.assert_not_called()
    assert plan.directories[0].exists()


def test_publication_change_refuses_all_deletion(harness: CleanupHarness) -> None:
    plan = harness.service.plan()
    changed = plan.state.model_copy(
        update={
            "topics": plan.state.topics.model_copy(update={"seq_no": 2}),
        }
    )
    with (
        patch.object(harness.service, "_state", return_value=changed),
        pytest.raises(ValueError, match="Publications changed"),
    ):
        harness.service.apply(plan)
    harness.client.delete_by_query.assert_not_called()
    harness.client.indices.delete.assert_not_called()


def test_cleanup_claim_excludes_other_analytics_atomically(
    harness: CleanupHarness,
) -> None:
    training = harness.store.create(JobKind.TOPIC_TRAINING, "training", {})
    harness.store.mark_running(training["id"], update_windows=False)
    cleanup = harness.store.create(
        JobKind.ANALYTICS_CLEANUP,
        "cleanup",
        CleanupRequest(request_id="explicit").model_dump(mode="json"),
    )
    with pytest.raises(JobSlotsBusy):
        harness.service.run(cleanup["id"])
    assert harness.store.get(cleanup["id"])["status"] == "queued"
    harness.client.delete_by_query.assert_not_called()
    harness.store.mark_succeeded(training["id"])
    harness.store.mark_running(
        cleanup["id"],
        update_windows=False,
        max_active=1,
        exclusive_kinds=JobKind.analytics(),
    )
    graph = harness.store.create(JobKind.MEMBER_GRAPH, "graph", {})
    with pytest.raises(JobSlotsBusy):
        harness.store.mark_running(
            graph["id"],
            update_windows=False,
            max_active=1,
            exclusive_kinds=JobKind.analytics(),
        )


@pytest.mark.parametrize("failure", ["partial", "conflict", "count"])
def test_incomplete_index_deletion_stops_before_removing_models(
    harness: CleanupHarness, failure: str
) -> None:
    plan = harness.service.plan()
    harness.client.delete_by_query.return_value = ObjectApiResponse(
        {
            "deleted": 6 if failure == "count" else 7,
            "timed_out": failure == "partial",
            "failures": [],
            "version_conflicts": int(failure == "conflict"),
        },
        Mock(),
    )
    with pytest.raises(RuntimeError, match="deletion"):
        harness.service.apply(plan)
    assert plan.directories[0].is_dir()
    harness.client.indices.delete.assert_not_called()


def test_cleanup_job_persists_result_only_after_verified_cleanup(
    harness: CleanupHarness,
) -> None:
    row = harness.store.create(
        JobKind.ANALYTICS_CLEANUP,
        "cleanup",
        CleanupRequest(request_id="explicit").model_dump(mode="json"),
    )
    assert harness.service.run(row["id"]).status == "succeeded"
    assert harness.store.get(row["id"])["status"] == "succeeded"


def test_truncated_generation_inventory_is_not_a_deletion_plan(
    harness: CleanupHarness,
) -> None:
    response = harness.search()
    response.body["aggregations"]["versions"]["sum_other_doc_count"] = 1
    harness.client.search.side_effect = None
    harness.client.search.return_value = response
    with pytest.raises(ValueError, match="truncated"):
        harness.service.plan()
    harness.client.delete_by_query.assert_not_called()


def test_failed_parent_never_permits_cleanup(harness: CleanupHarness) -> None:
    parent = harness.store.create(JobKind.TOPIC_TRAINING, "parent", {})
    harness.store.mark_failed(parent["id"], "training failed")
    row = harness.store.create(
        JobKind.ANALYTICS_CLEANUP,
        "cleanup",
        CleanupRequest(request_id="explicit", parent_job_id=parent["id"]).model_dump(
            mode="json"
        ),
    )
    with pytest.raises(ValueError, match="successful analytics parent"):
        harness.service.run(row["id"])
    harness.client.delete_by_query.assert_not_called()

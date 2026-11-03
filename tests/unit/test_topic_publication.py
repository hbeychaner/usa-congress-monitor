from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from elasticsearch import Elasticsearch, NotFoundError

from cdm.backend.services.subject_service import SubjectService
from cdm.backend.services.topic_service import TopicService
from cdm.config.topic_analysis import TopicPublicationId
from cdm.graph.topics import TopicModelReader
from cdm.store.metasubject_repository import MetasubjectRepository
from cdm.store.topic_publication import (
    CompletedTopicRun,
    TopicPublicationPointer,
    TopicPublicationStore,
    TopicRunCounts,
    TopicRunSpecification,
)
from cdm.utils.json_types import JsonObject


@pytest.fixture
def completed() -> CompletedTopicRun:
    return CompletedTopicRun(
        model_version="complete",
        trained_at=datetime(2026, 11, 2, tzinfo=UTC),
        completed_at=datetime(2026, 11, 2, 1, tzinfo=UTC),
        embedding_model="configured-model",
        min_congress=113,
        corpus_size=1,
        dated_documents=1,
        model_path="models/topics/complete",
        counts=TopicRunCounts(
            topics=1,
            assignments=1,
            over_time=1,
            metasubjects=1,
            metasubject_over_time=1,
        ),
    )


def count_response(run: TopicRunSpecification) -> JsonObject:
    return {
        "aggregations": {
            "counts": {
                "buckets": [
                    {"key": kind, "doc_count": count}
                    for kind, count in run.counts.by_kind().items()
                ]
            }
        }
    }


def missing() -> NotFoundError:
    return NotFoundError("missing", meta=Mock(status=404), body={})


@pytest.fixture
def client(completed: CompletedTopicRun) -> Mock:
    client = Mock(spec=Elasticsearch, indices=Mock())
    client.indices.exists.return_value = True
    client.get.return_value = {
        "_source": TopicPublicationPointer(run=completed).model_dump(mode="json"),
        "_seq_no": 3,
        "_primary_term": 1,
    }
    client.search.return_value = count_response(completed)
    return client


class TestPublishedReaders:
    def test_api_and_graph_ignore_newer_uncommitted_rows(self, client: Mock) -> None:
        client.search.return_value = {
            "hits": {"hits": [{"_source": {"model_version": "newer-partial"}}]}
        }

        assert TopicModelReader(client, "analysis").latest_version() == "complete"
        service = TopicService(client, "analysis", Mock(spec=SubjectService))
        assert service.latest_model_version()[0] == "complete"
        client.search.assert_not_called()

    def test_metasubjects_are_filtered_to_the_published_run(
        self, client: Mock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scan = Mock(return_value=[])
        monkeypatch.setattr("cdm.store.metasubject_repository.scan", scan)

        assert MetasubjectRepository(client, "analysis").latest() == []
        assert {"term": {"model_version": "complete"}} in (
            scan.call_args.kwargs["query"]["query"]["bool"]["filter"]
        )

    def test_legacy_rows_are_not_an_implicit_publication(self, client: Mock) -> None:
        client.get.side_effect = missing()

        assert TopicModelReader(client, "analysis").latest_version() is None
        assert TopicService(
            client, "analysis", Mock(spec=SubjectService)
        ).latest_model_version() == (None, None)
        assert MetasubjectRepository(client, "analysis").latest() == []
        client.search.assert_not_called()

    def test_dependency_failure_is_not_reported_as_no_model(self, client: Mock) -> None:
        client.get.side_effect = RuntimeError("unavailable")

        with pytest.raises(RuntimeError, match="unavailable"):
            TopicPublicationStore(client, "analysis").current()


class TestCompleteRunWrites:
    @pytest.mark.parametrize(
        ("corpus_size", "dated_documents", "message"),
        [(2, 1, "Assignment count"), (1, 2, "Dated documents")],
    )
    def test_manifest_rejects_inconsistent_corpus_counts(
        self,
        completed: CompletedTopicRun,
        corpus_size: int,
        dated_documents: int,
        message: str,
    ) -> None:
        with pytest.raises(ValueError, match=message):
            TopicRunSpecification.model_validate(
                {
                    **completed.model_dump(),
                    "corpus_size": corpus_size,
                    "dated_documents": dated_documents,
                }
            )

    def test_partial_bulk_never_writes_a_manifest_or_pointer(
        self,
        client: Mock,
        completed: CompletedTopicRun,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            "cdm.store.topic_publication.bulk",
            Mock(return_value=(1, [{"create": {"status": 400}}])),
        )
        store = TopicPublicationStore(client, "analysis")

        with pytest.raises(RuntimeError, match="Incomplete topic bulk"):
            store.write(completed, [])

        client.index.assert_not_called()
        current = store.current()
        assert current is not None
        assert current.model_version == completed.model_version

    def test_bulk_count_must_match_all_expected_kinds(
        self,
        client: Mock,
        completed: CompletedTopicRun,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            "cdm.store.topic_publication.bulk",
            Mock(return_value=(completed.counts.total, [])),
        )
        client.search.return_value = {"aggregations": {"counts": {"buckets": []}}}

        with pytest.raises(ValueError, match="Incomplete topic run"):
            TopicPublicationStore(client, "analysis").write(completed, [])

        client.index.assert_not_called()

    def test_success_only_creates_an_immutable_manifest(
        self,
        client: Mock,
        completed: CompletedTopicRun,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        bulk = Mock(return_value=(completed.counts.total, []))
        monkeypatch.setattr("cdm.store.topic_publication.bulk", bulk)
        specification = TopicRunSpecification.model_validate(completed.model_dump())
        store = TopicPublicationStore(client, "analysis")

        result = store.write(specification, [{"_index": "analysis", "_id": "row"}])

        assert next(iter(bulk.call_args.args[1]))["_op_type"] == "create"
        assert result.model_version == completed.model_version
        client.index.assert_called_once()
        assert client.index.call_args.kwargs["id"] == completed.id
        assert client.index.call_args.kwargs["op_type"] == "create"
        assert client.index.call_args.kwargs["id"] != TopicPublicationId.CURRENT


class TestPointerPublication:
    def test_existing_pointer_uses_compare_and_swap(
        self, client: Mock, completed: CompletedTopicRun
    ) -> None:
        store = TopicPublicationStore(client, "analysis")
        baseline = store.snapshot()
        client.get.return_value = {"_source": completed.model_dump(mode="json")}

        store.publish(completed.model_version, baseline)

        arguments = client.index.call_args.kwargs
        assert arguments["if_seq_no"] == 3
        assert arguments["if_primary_term"] == 1
        assert arguments["id"] == TopicPublicationId.CURRENT
        assert "op_type" not in arguments

    def test_first_publication_cannot_overwrite_a_concurrent_pointer(
        self, client: Mock, completed: CompletedTopicRun
    ) -> None:
        client.get.return_value = {"_source": completed.model_dump(mode="json")}

        TopicPublicationStore(client, "analysis").publish(completed.model_version, None)

        assert client.index.call_args.kwargs["op_type"] == "create"

    def test_legacy_version_without_manifest_cannot_be_published(
        self, client: Mock
    ) -> None:
        client.get.side_effect = missing()

        with pytest.raises(ValueError, match="No validated complete topic run"):
            TopicPublicationStore(client, "analysis").publish("legacy", None)

        client.index.assert_not_called()

    def test_rollback_rechecks_that_data_is_still_complete(
        self, client: Mock, completed: CompletedTopicRun
    ) -> None:
        store = TopicPublicationStore(client, "analysis")
        baseline = store.snapshot()
        client.get.return_value = {"_source": completed.model_dump(mode="json")}
        client.search.return_value = {"aggregations": {"counts": {"buckets": []}}}

        with pytest.raises(ValueError, match="Incomplete topic run"):
            store.publish(completed.model_version, baseline)

        client.index.assert_not_called()

    def test_switching_embedding_models_requires_a_migration(
        self, client: Mock, completed: CompletedTopicRun
    ) -> None:
        store = TopicPublicationStore(client, "analysis")
        baseline = store.snapshot()
        other = completed.model_copy(update={"embedding_model": "different-model"})
        client.get.return_value = {"_source": other.model_dump(mode="json")}

        with pytest.raises(ValueError, match="cache migration"):
            store.publish(other.model_version, baseline)

        client.index.assert_not_called()

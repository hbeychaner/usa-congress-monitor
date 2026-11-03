from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from elastic_transport import ObjectApiResponse
from elasticsearch import Elasticsearch, NotFoundError
from pydantic import ValidationError

from cdm.config import PerspectiveConfig
from cdm.config.topic_analysis import PerspectiveKind
from cdm.graph.topics import TopicModelReader
from cdm.jobs.analytics import PerspectiveRequest
from cdm.perspectives.boilerplate import BoilerplateLearner
from cdm.perspectives.builder import PerspectiveBuilder
from cdm.perspectives.corpus import CongressCorpus, CongressCorpusReader
from cdm.perspectives.job import PerspectiveBuildJob
from cdm.perspectives.lexicon import BoilerplateLexicon
from cdm.perspectives.models import PerspectiveBill, TopicPerspectives
from cdm.perspectives.runner import NoTopicModelError, PerspectiveRunner
from cdm.store.perspective_repository import PerspectiveRepository
from cdm.workers.analytics_runner import AnalysisCancelled


@pytest.fixture
def client() -> Mock:
    client = Mock(spec=Elasticsearch, indices=Mock())
    client.indices.exists.return_value = True
    return client


def topic(congress: int = 119, topic_id: int = 1) -> TopicPerspectives:
    return TopicPerspectives(
        congress=congress, topic_id=topic_id, topic_label="Health", bills=1
    )


def test_empty_refresh_does_not_delete_previous_rows(client: Mock) -> None:
    repository = PerspectiveRepository(client, "analysis")

    assert (
        repository.replace(119, "source-model", datetime(2026, 11, 2, tzinfo=UTC), [])
        == 0
    )

    client.delete_by_query.assert_not_called()
    client.index.assert_called_once()
    assert client.index.call_args.kwargs["document"]["results"] == []


def test_snapshot_read_does_not_scan_or_mix_legacy_rows(client: Mock) -> None:
    repository = PerspectiveRepository(client, "analysis")
    repository.replace(119, "source-model", datetime.now(UTC), [topic()])
    client.get.return_value = {"_source": client.index.call_args.kwargs["document"]}

    assert repository.read(119) == ([topic()], "source-model")
    assert client.get.call_args.kwargs["id"] == "party_topic_publication:119"
    client.search.assert_not_called()


def test_empty_snapshot_keeps_its_source_identity(client: Mock) -> None:
    repository = PerspectiveRepository(client, "analysis")
    repository.replace(119, "empty-model", datetime.now(UTC), [])
    client.get.return_value = {"_source": client.index.call_args.kwargs["document"]}
    assert repository.read(119) == ([], "empty-model")
    client.search.assert_not_called()


def test_legacy_rows_remain_readable_without_a_snapshot(client: Mock) -> None:
    client.get.side_effect = NotFoundError("missing", meta=Mock(status=404), body={})
    client.search.return_value = ObjectApiResponse(
        {
            "timed_out": False,
            "_shards": {"failed": 0},
            "hits": {
                "hits": [
                    {
                        "_source": {
                            **topic().model_dump(mode="json"),
                            "model_version": "legacy",
                        }
                    }
                ]
            },
        },
        Mock(),
    )
    assert PerspectiveRepository(client, "analysis").read(119) == ([topic()], "legacy")
    assert client.search.call_args.kwargs["allow_partial_search_results"] is False
    assert {"term": {"kind": PerspectiveKind.PARTY_TOPIC}} in (
        client.search.call_args.kwargs["query"]["bool"]["filter"]
    )


@pytest.mark.parametrize("results", [[topic(118)], [topic(), topic()]])
def test_incoherent_snapshots_fail_before_any_write(
    client: Mock,
    results: list[TopicPerspectives],
) -> None:
    with pytest.raises(ValidationError):
        PerspectiveRepository(client, "analysis").replace(
            119, "model", datetime.now(UTC), results
        )
    assert client.method_calls == []


def test_corrupt_snapshot_is_not_hidden_by_legacy_fallback(client: Mock) -> None:
    repository = PerspectiveRepository(client, "analysis")
    repository.replace(118, "other-congress", datetime.now(UTC), [topic(118)])
    client.get.return_value = {"_source": client.index.call_args.kwargs["document"]}
    with pytest.raises(ValueError, match="identity"):
        repository.read(119)
    client.search.assert_not_called()


def test_dependency_failure_does_not_fall_back_to_legacy_rows(client: Mock) -> None:
    client.get.side_effect = RuntimeError("unavailable")
    with pytest.raises(RuntimeError, match="unavailable"):
        PerspectiveRepository(client, "analysis").read(119)
    client.search.assert_not_called()


def test_failed_publication_is_explicit_and_never_deletes(client: Mock) -> None:
    client.index.side_effect = RuntimeError("write rejected")
    with pytest.raises(RuntimeError, match="write rejected"):
        PerspectiveRepository(client, "analysis").replace(
            119, "model", datetime.now(UTC), [topic()]
        )
    client.delete_by_query.assert_not_called()


def test_snapshot_has_no_legacy_search_window_truncation(client: Mock) -> None:
    results = [topic(topic_id=topic_id) for topic_id in range(10001)]
    repository = PerspectiveRepository(client, "analysis")
    assert repository.replace(119, "large", datetime.now(UTC), results) == 10001
    client.get.return_value = {"_source": client.index.call_args.kwargs["document"]}
    assert len(repository.read(119)[0]) == 10001


def test_congress_listing_includes_snapshots_and_untouched_legacy_rows(
    client: Mock,
) -> None:
    client.search.return_value = ObjectApiResponse(
        {
            "timed_out": False,
            "_shards": {"failed": 0},
            "aggregations": {"congresses": {"buckets": [{"key": 118}, {"key": 119}]}},
        },
        Mock(),
    )
    assert PerspectiveRepository(client, "analysis").congresses() == [119, 118]
    query = client.search.call_args.kwargs
    assert set(query["query"]["terms"]["kind"]) == set(PerspectiveKind)
    assert query["allow_partial_search_results"] is False


def test_whole_request_pins_one_model_for_multiple_congresses() -> None:
    runner = Mock(spec=PerspectiveRunner)
    runner.source_version.side_effect = ["pinned-model", "newly-published-model"]
    runner.run.side_effect = [[topic(118)], [topic(119)]]
    repository = Mock(spec=PerspectiveRepository)
    repository.replace.return_value = 1
    job = PerspectiveBuildJob(runner, repository, lambda _progress: None)

    job.run(PerspectiveRequest(congresses=[118, 119]))

    runner.source_version.assert_called_once_with()
    assert [call.kwargs["model_version"] for call in runner.run.call_args_list] == [
        "pinned-model",
        "pinned-model",
    ]
    assert [call.args[:2] for call in repository.replace.call_args_list] == [
        (118, "pinned-model"),
        (119, "pinned-model"),
    ]


def test_cancellation_checkpoint_prevents_snapshot_publication() -> None:
    runner = Mock(spec=PerspectiveRunner)
    runner.source_version.return_value = "pinned-model"
    runner.run.return_value = [topic()]
    repository = Mock(spec=PerspectiveRepository)
    report = Mock(side_effect=[None, AnalysisCancelled()])
    job = PerspectiveBuildJob(runner, repository, report)
    with pytest.raises(AnalysisCancelled):
        job.run(PerspectiveRequest(congresses=[119]))
    repository.replace.assert_not_called()


def test_repeated_builds_reread_current_congress_sources() -> None:
    topics = Mock(spec=TopicModelReader)
    topics.assignments.return_value = {"bill": 1}
    topics.labels.return_value = {1: "Health"}
    corpus = Mock(spec=CongressCorpusReader)
    corpus.read.side_effect = [
        CongressCorpus(
            congress=119,
            bills={
                "bill": PerspectiveBill(
                    doc_id="bill",
                    title=text,
                    text=text,
                )
            },
            documents={},
        )
        for text in ("original text", "updated daily text")
    ]
    learner = Mock(spec=BoilerplateLearner)
    learner.learn.return_value = BoilerplateLexicon()
    builder = Mock(spec=PerspectiveBuilder)
    builder.build.return_value = topic()
    runner = PerspectiveRunner(
        PerspectiveConfig(perspective_min_topic_bills=1),
        topics,
        corpus,
        learner,
        Mock(return_value=builder),
    )

    runner.run(119, "pinned-model")
    runner.run(119, "pinned-model")

    assert corpus.read.call_count == 2
    assert [call.kwargs["bills"][0].text for call in builder.build.call_args_list] == [
        "original text",
        "updated daily text",
    ]
    topics.latest_version.assert_not_called()
    assert all(
        call.args == ("pinned-model",) for call in topics.assignments.call_args_list
    )


def test_missing_source_model_fails_before_building() -> None:
    topics = Mock(spec=TopicModelReader)
    topics.latest_version.return_value = None
    corpus = Mock(spec=CongressCorpusReader)
    runner = PerspectiveRunner(
        PerspectiveConfig(),
        topics,
        corpus,
        Mock(spec=BoilerplateLearner),
        Mock(),
    )
    with pytest.raises(NoTopicModelError, match="no trained topic model"):
        runner.source_version()
    corpus.read.assert_not_called()

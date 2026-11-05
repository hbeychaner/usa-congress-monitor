from collections.abc import Iterable
from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from elastic_transport import ApiResponseMeta, HttpHeaders, NodeConfig
from elasticsearch import Elasticsearch, NotFoundError

from cdm.config.topic_analysis import GraphStoreConfig
from cdm.graph.job import GraphBuildJob
from cdm.graph.models import (
    BillSignature,
    CongressEdgeStats,
    GraphMapping,
    GraphVersionPointer,
    MappingField,
    MemberEdge,
    RollCallVotes,
    Signal,
)
from cdm.graph.store import BillSignatureReader, GraphStore, RollCallReader
from cdm.graph.topics import TopicModelReader
from cdm.store.index_manager import load_definitions


@pytest.fixture
def graph_client() -> Mock:
    client = Mock(spec=Elasticsearch)
    client.indices = Mock()
    client.indices.get_mapping.return_value.body = {
        GraphStore(client).index: load_definitions()["analysis_graph"]
    }
    client.get.side_effect = NotFoundError(
        "missing",
        ApiResponseMeta(404, "1.1", HttpHeaders(), 0, NodeConfig("http", "localhost", 9200)),
        {"found": False},
    )
    return client


class GraphFixture:
    def __init__(self) -> None:
        self.store: Mock = Mock(spec=GraphStore)
        self.bills: Mock = Mock(spec=BillSignatureReader)
        self.rolls: Mock = Mock(spec=RollCallReader)
        self.topics: Mock = Mock(spec=TopicModelReader)
        bills: list[BillSignature] = [
            BillSignature(
                id="a",
                congress=118,
                sponsor_bioguide_ids=["A"],
                cosponsor_bioguide_ids=["B"],
            ),
            BillSignature(
                id="b",
                congress=117,
                sponsor_bioguide_ids=["B"],
                cosponsor_bioguide_ids=["A"],
            ),
            BillSignature(id="c", congress=118, sponsor_bioguide_ids=["A"]),
        ]
        self.bills.read.return_value = bills
        self.rolls.read.return_value = [
            RollCallVotes(congress=119, party_split=True, yea_ids=["A", "B"])
        ]
        self.topics.latest_version.side_effect = [
            "source-model",
            "unexpected-new-model",
        ]
        self.topics.assignments.return_value = {"a": 1, "b": 1, "c": 2}
        self.topics.labels.return_value = {1: "Health", 2: "Tax"}
        self.edges: list[MemberEdge] = []
        self.store.write_edges.side_effect = self.write
        self.job = GraphBuildJob(
            self.store, self.bills, self.rolls, self.topics, lambda _progress: None
        )

    def write(self, edges: Iterable[MemberEdge]) -> int:
        batch = list(edges)
        self.edges.extend(batch)
        return len(batch)


def test_stage_writes_candidate_without_publishing() -> None:
    fixture = GraphFixture()
    staged = fixture.job.stage(Signal.VOTING)
    assert staged.written == len(fixture.edges) > 0
    assert staged.pointer.congresses == [119]
    fixture.store.publish.assert_not_called()


def test_build_records_actual_scope_and_pins_topic_reads() -> None:
    graph = GraphFixture()
    versions = graph.job.run()
    pointers = {
        call.args[0].signal: call.args[0] for call in graph.store.publish.call_args_list
    }

    assert set(versions) == set(Signal)
    assert pointers[Signal.VOTING].congresses == [119]
    for signal in (Signal.COLLABORATION, Signal.TOPIC):
        assert pointers[signal].congresses == [117, 118]
    assert pointers[Signal.TOPIC].source_model_version == "source-model"
    assert pointers[Signal.VOTING].source_model_version is None
    assert pointers[Signal.COLLABORATION].source_model_version is None
    graph.topics.latest_version.assert_called_once_with()
    graph.topics.assignments.assert_called_once_with("source-model")
    graph.topics.labels.assert_called_once_with("source-model")
    assert {edge.signal for edge in graph.edges} == set(Signal)
    assert all(edge.graph_version == versions[edge.signal] for edge in graph.edges)
    assert [call[0] for call in graph.store.method_calls] == [
        "ensure_index",
        "pointer_snapshot",
        "write_edges",
        "publish",
        "pointer_snapshot",
        "write_edges",
        "publish",
        "pointer_snapshot",
        "write_edges",
        "publish",
    ]


def test_graph_versions_are_unique_even_with_the_same_clock() -> None:
    graph = GraphFixture()
    with patch("cdm.graph.job.datetime") as clock:
        clock.now.return_value = datetime(2026, 1, 1, tzinfo=UTC)
        first = graph.job.run([Signal.VOTING])
        second = graph.job.run([Signal.VOTING])
    assert first[Signal.VOTING] != second[Signal.VOTING]


def test_missing_topic_model_does_not_publish() -> None:
    graph = GraphFixture()
    graph.topics.latest_version.side_effect = None
    graph.topics.latest_version.return_value = None
    with pytest.raises(RuntimeError, match="no trained topic model"):
        graph.job.run([Signal.TOPIC])
    graph.store.write_edges.assert_not_called()
    graph.store.publish.assert_not_called()


def test_failed_edge_write_does_not_publish() -> None:
    graph = GraphFixture()
    graph.store.write_edges.side_effect = RuntimeError("partial graph bulk")
    with pytest.raises(RuntimeError, match="partial graph bulk"):
        graph.job.run([Signal.VOTING])
    graph.store.publish.assert_not_called()


def test_publish_refreshes_staged_edges_before_pointer_write(
    graph_client: Mock,
) -> None:
    client = graph_client
    client.indices.refresh.return_value = {"_shards": {"failed": 0}}
    store = GraphStore(client)
    pointer = GraphVersionPointer(
        signal=Signal.TOPIC,
        graph_version="graph-uuid",
        source_model_version="topic-uuid",
        congresses=[117, 118],
    )
    store.publish(pointer)

    assert [call[0] for call in client.method_calls] == [
        "indices.get_mapping",
        "indices.refresh",
        "get",
        "index",
    ]
    assert client.index.call_args.kwargs == {
        "index": store.index,
        "id": pointer.id,
        "document": pointer.model_dump(mode="json"),
        "op_type": "create",
        "refresh": True,
    }


def test_failed_refresh_leaves_pointer_untouched(graph_client: Mock) -> None:
    client = graph_client
    client.indices.refresh.side_effect = RuntimeError("incomplete refresh")
    with pytest.raises(RuntimeError, match="incomplete refresh"):
        GraphStore(client).publish(
            GraphVersionPointer(signal=Signal.TOPIC, graph_version="not-visible")
        )
    client.index.assert_not_called()


def test_partial_refresh_leaves_pointer_untouched(graph_client: Mock) -> None:
    client = graph_client
    client.indices.refresh.return_value = {"_shards": {"failed": 1}}
    with pytest.raises(RuntimeError, match="Graph refresh failed"):
        GraphStore(client).publish(
            GraphVersionPointer(signal=Signal.TOPIC, graph_version="partially-visible")
        )
    client.index.assert_not_called()


@pytest.mark.parametrize("reader_class", [BillSignatureReader, RollCallReader])
def test_source_reads_are_scoped_and_reject_partial_results(
    reader_class: type[BillSignatureReader] | type[RollCallReader],
) -> None:
    settings = GraphStoreConfig(first_congress=118)
    reader = reader_class(Mock(spec=Elasticsearch), settings)
    with patch("cdm.graph.store.scan", return_value=iter(())) as scan:
        assert list(reader.read()) == []
    assert reader.first_congress == 118
    assert scan.call_args.kwargs["allow_partial_search_results"] is False
    assert "write" not in scan.call_args.kwargs["index"]


def test_serialized_graph_models_are_fully_declared() -> None:
    properties = load_definitions()["analysis_graph"]["mappings"]["properties"]
    edge = MemberEdge(
        graph_version="v", signal=Signal.VOTING, member="A", neighbor="B", score=0.5
    )
    pointer = GraphVersionPointer(signal=Signal.VOTING, graph_version="v")
    assert set(edge.model_dump()) <= set(properties)
    assert set(pointer.model_dump()) <= set(properties)
    assert set(CongressEdgeStats(congress=114).model_dump()) <= set(
        properties["by_congress"]["properties"]
    )


@pytest.mark.parametrize("positions", [[], ["A"]])
def test_roll_reader_rejects_unlinked_inputs_but_accepts_present_voters(
    positions: list[str],
) -> None:
    reader = RollCallReader(Mock(spec=Elasticsearch))
    with patch(
        "cdm.graph.store.scan",
        return_value=iter(
            [
                {
                    "_id": "rollcall:114:house:1",
                    "_source": {"congress": 114, "present_ids": positions},
                }
            ]
        ),
    ):
        if positions:
            assert next(reader.read()).present_ids == positions
        else:
            with pytest.raises(ValueError, match="no linked member positions"):
                list(reader.read())


def test_graph_schema_rejects_disabled_or_wrong_nested_fields() -> None:
    expected = GraphMapping.model_validate(
        load_definitions()["analysis_graph"]["mappings"]
    )
    actual = expected.model_copy(deep=True)
    actual.properties[MappingField("by_congress")].type = "object"
    actual.properties[MappingField("shared_topics")].index = False
    assert expected.differences(actual) == [
        "shared_topics: incompatible mapping",
        "by_congress: incompatible mapping",
    ]


def test_topic_source_reads_reject_partial_results() -> None:
    reader = TopicModelReader(Mock(spec=Elasticsearch), "topics")
    with patch("cdm.graph.topics.scan", return_value=iter(())) as scan:
        assert reader.assignments("version") == {}
    assert scan.call_args.kwargs["allow_partial_search_results"] is False

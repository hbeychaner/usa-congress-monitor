import os
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from elasticsearch import ApiError, ConflictError, Elasticsearch

from cdm.config.topic_analysis import GraphStoreConfig
from cdm.graph.job import GraphBuildJob
from cdm.graph.models import CongressEdgeStats, GraphVersionPointer, MemberEdge, Signal
from cdm.graph.store import BillSignatureReader, GraphStore, RollCallReader
from cdm.graph.topics import TopicModelReader
from cdm.ingest.voteview import RollCallBuilder
from cdm.store.index_manager import load_definitions
from cdm.store.opensearch import bulk_upsert, read_alias, write_alias


@pytest.fixture
def store() -> Iterator[GraphStore]:
    url = os.environ.get("GRAPH_PUBLICATION_TEST_URL")
    if not url:
        pytest.skip(
            "Set GRAPH_PUBLICATION_TEST_URL to an isolated Elasticsearch server"
        )
    client = Elasticsearch(
        url,
        request_timeout=30,
        api_key=os.environ.get("GRAPH_PUBLICATION_TEST_API_KEY") or None,
    )
    settings = GraphStoreConfig(index=f"graph-lineage-test-{uuid4().hex}")
    store = GraphStore(client, settings)
    client.indices.create(
        index=store.index,
        **load_definitions()["analysis_graph"],
        aliases={read_alias(settings.index): {}, write_alias(settings.index): {}},
    )
    try:
        yield store
    finally:
        client.indices.delete(index=store.index, ignore_unavailable=True)
        client.close()


def publish(store: GraphStore, version: str) -> GraphVersionPointer:
    pointer = GraphVersionPointer(
        signal=Signal.TOPIC,
        graph_version=version,
        source_model_version=f"model-{version}",
        congresses=[117, 118],
    )
    assert (
        store.write_edges(
            [
                MemberEdge(
                    graph_version=version,
                    signal=Signal.TOPIC,
                    member="A",
                    neighbor="B",
                    score=0.5,
                )
            ]
        )
        == 1
    )
    store.publish(pointer)
    return pointer


def test_published_lineage_round_trips_and_prior_versions_remain(
    store: GraphStore,
) -> None:
    pointers = [publish(store, f"version-{number}") for number in range(5)]
    assert store.active_pointer(Signal.TOPIC) == pointers[-1]
    assert store.active_version(Signal.TOPIC) == pointers[-1].graph_version
    for pointer in pointers:
        assert store.edge_count(pointer.signal, pointer.graph_version) == 1


def test_stale_create_update_and_signal_scoped_rollback(store: GraphStore) -> None:
    absent = store.pointer_snapshot(Signal.TOPIC)
    original = publish(store, "cas-original")
    original_snapshot = store.pointer_snapshot(Signal.TOPIC)
    newer = publish(store, "cas-newer")
    with pytest.raises(ConflictError):
        store.publish(original, expected=absent)
    with pytest.raises(ConflictError):
        store.publish(original, expected=original_snapshot)
    assert store.active_pointer(Signal.TOPIC) == newer
    current = store.pointer_snapshot(Signal.TOPIC)
    store.publish(original, expected=current)
    assert store.active_pointer(Signal.TOPIC) == original
    store.publish(newer, expected=store.pointer_snapshot(Signal.TOPIC))
    assert store.active_pointer(Signal.TOPIC) == newer
    assert store.edge_count(Signal.TOPIC, original.graph_version) == 1


def test_staged_edges_are_visible_when_pointer_is_published(store: GraphStore) -> None:
    store.client.indices.put_settings(
        index=store.index, settings={"index.refresh_interval": "-1"}
    )
    pointer = publish(store, "fresh")
    assert store.edge_count(Signal.TOPIC, pointer.graph_version) == 1


def test_publication_failure_preserves_previous_pointer_and_edges(
    store: GraphStore,
) -> None:
    original = publish(store, "original")
    store.client.indices.put_settings(
        index=store.index, settings={"index.blocks.write": True}
    )
    with pytest.raises(ApiError):
        store.publish(GraphVersionPointer(signal=Signal.TOPIC, graph_version="blocked"))
    with pytest.raises(RuntimeError, match="Bulk indexing failed"):
        publish(store, "blocked")
    assert store.active_pointer(Signal.TOPIC) == original
    assert store.edge_count(Signal.TOPIC, "original") == 1


def test_refresh_failure_does_not_replace_published_pointer(store: GraphStore) -> None:
    original = publish(store, "original")
    with (
        patch.object(
            store.client.indices, "refresh", side_effect=RuntimeError("refresh")
        ),
        pytest.raises(RuntimeError, match="refresh"),
    ):
        publish(store, "staged")
    assert store.active_pointer(Signal.TOPIC) == original
    assert store.client.exists(index=store.index, id="edge:staged:topic:A:B")


def test_missing_graph_reports_explicit_schema_failure(store: GraphStore) -> None:
    store.client.indices.delete(index=store.index)
    assert store.schema_errors() == [f"{store.index}: missing graph index"]


def test_existing_graph_preflight_does_not_mutate_schema_or_aliases(
    store: GraphStore,
) -> None:
    before = store.client.indices.get(index=store.index).body
    store.ensure_index()
    assert store.client.indices.get(index=store.index).body == before


def test_edges_and_pointer_remain_colocated_when_write_alias_diverges(
    store: GraphStore,
) -> None:
    other = f"{store.index}-other"
    client = store.client
    client.indices.create(index=other, **load_definitions()["analysis_graph"])
    try:
        alias = write_alias(store._settings.index)
        client.indices.update_aliases(
            actions=[
                {"remove": {"index": store.index, "alias": alias}},
                {"add": {"index": other, "alias": alias}},
            ]
        )
        pointer = publish(store, "colocated")
        assert store.edge_count(pointer.signal, pointer.graph_version) == 1
        assert client.count(index=other)["count"] == 0
    finally:
        client.indices.delete(index=other)


def test_publishing_does_not_change_source_records(store: GraphStore) -> None:
    source_index = f"{store.index}-source"
    source = {"source_type": "bill", "congress": 118, "title": "Source record"}
    store.client.indices.create(index=source_index)
    try:
        store.client.index(index=source_index, id="bill", document=source)
        publish(store, "replacement")
        assert store.client.get(index=source_index, id="bill")["_source"] == source
    finally:
        store.client.indices.delete(index=source_index)


@pytest.mark.parametrize("drift", ["missing", "nested", "unsearchable"])
def test_incompatible_schema_blocks_writes_and_publication_without_repair(
    store: GraphStore, drift: str
) -> None:
    definition = deepcopy(load_definitions()["analysis_graph"])
    properties = definition["mappings"]["properties"]
    if drift == "missing":
        del properties["by_congress"]["properties"]["shared_votes"]
    elif drift == "nested":
        properties["by_congress"]["type"] = "object"
    else:
        properties["shared_topics"]["index"] = False
    store.client.indices.delete(index=store.index)
    store.client.indices.create(index=store.index, **definition)
    original = GraphVersionPointer(signal=Signal.VOTING, graph_version="original")
    store.client.index(
        index=store.index,
        id=original.id,
        document=original.model_dump(mode="json"),
        refresh=True,
    )
    before = store.client.indices.get_mapping(index=store.index).body
    assert store.schema_errors()
    with pytest.raises(ValueError, match="approved schema migration required"):
        store.ensure_index()
    with pytest.raises(ValueError, match="approved schema migration required"):
        store.write_edges(
            [
                MemberEdge(
                    graph_version="replacement",
                    signal=Signal.VOTING,
                    member="A",
                    neighbor="B",
                    score=0.5,
                )
            ]
        )
    with pytest.raises(ValueError, match="approved schema migration required"):
        store.publish(
            GraphVersionPointer(signal=Signal.VOTING, graph_version="replacement")
        )
    assert store.active_pointer(Signal.VOTING) == original
    assert store.client.count(index=store.index)["count"] == 1
    assert store.client.indices.get_mapping(index=store.index).body == before


def test_decimal_csv_ids_recover_voting_graph_through_real_source_index(
    store: GraphStore, tmp_path: Path
) -> None:
    members, rolls, votes = (tmp_path / name for name in ("m.csv", "r.csv", "v.csv"))
    members.write_text(
        "chamber,icpsr,party_code,bioguide_id\nHouse,1,100,A\nHouse,2,200,B\n"
    )
    rolls.write_text("congress,chamber,rollnumber\n114,House,1\n")
    votes.write_text("rollnumber,icpsr,cast_code\n1,1.0,1\n1,2.0,6\n")
    source_index = f"graph-vote-source-{uuid4().hex}"
    client = store.client
    client.indices.create(
        index=source_index,
        **load_definitions()["rollcall"],
    )
    try:
        documents = [
            document.to_index_document()
            for document in RollCallBuilder(members, rolls, votes).build()
        ]
        bulk_upsert(
            client, "rollcall", documents, replace=True, target_index=source_index
        )
        client.indices.refresh(index=source_index)
        job = GraphBuildJob(
            store,
            Mock(spec=BillSignatureReader),
            RollCallReader(client, index=source_index),
            Mock(spec=TopicModelReader),
            lambda _progress: None,
        )
        versions = job.run([Signal.VOTING])
        pointer = store.active_pointer(Signal.VOTING)
        assert pointer is not None
        assert pointer.congresses == [114]
        assert store.edge_count(Signal.VOTING, versions[Signal.VOTING]) == 2
        assert (
            client.count(index=store.index, query={"term": {"shared_votes": 1}})[
                "count"
            ]
            == 2
        )
    finally:
        client.indices.delete(index=source_index)


def test_graph_fields_are_searchable_not_merely_retained_in_source(
    store: GraphStore,
) -> None:
    edge = MemberEdge(
        graph_version="searchable",
        signal=Signal.TOPIC,
        member="A",
        neighbor="B",
        score=0.5,
        shared_topics=["Health"],
        by_congress=[
            CongressEdgeStats(
                congress=114,
                shared_votes=5,
                agreed_votes=4,
                shared_split_votes=3,
                agreed_split_votes=2,
            )
        ],
    )
    store.write_edges([edge])
    store.publish(
        GraphVersionPointer(
            signal=Signal.TOPIC,
            graph_version="searchable",
            source_model_version="source",
            congresses=[114],
        )
    )
    client, index = store.client, store.index
    for field, value in [
        ("shared_topics", "Health"),
        ("shared_votes", 5),
        ("source_model_version", "source"),
        ("congresses", 114),
    ]:
        assert client.count(index=index, query={"term": {field: value}})["count"] == 1
    assert (
        client.count(
            index=index,
            query={
                "nested": {
                    "path": "by_congress",
                    "query": {
                        "bool": {
                            "filter": [
                                {"term": {f"by_congress.{field}": value}}
                                for field, value in [
                                    ("shared_votes", 5),
                                    ("agreed_votes", 4),
                                    ("shared_split_votes", 3),
                                    ("agreed_split_votes", 2),
                                ]
                            ]
                        }
                    },
                }
            },
        )["count"]
        == 1
    )

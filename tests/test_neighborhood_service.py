from typing import cast
from unittest.mock import Mock

import pytest
from elastic_transport import ObjectApiResponse

from cdm.backend.services.graph_service import (
    GraphReadSnapshot,
    GraphService,
)
from cdm.backend.services.member_service import MemberService
from cdm.backend.services.neighborhood_service import (
    NeighborhoodQuery,
    NeighborhoodService,
)
from cdm.config.query_reads import QueryReadConfig
from cdm.contracts.api import MemberSummary
from cdm.graph.models import GraphVersionPointer, MemberEdge, PartyGroup, Signal
from cdm.graph.store import GraphStore
from cdm.store.topic_publication import TopicPublicationStore


def _edge(signal: Signal, member: str, neighbor: str, score: float) -> MemberEdge:
    return MemberEdge(
        graph_version="v1", signal=signal, member=member, neighbor=neighbor, score=score
    )


def _summary(member_id: str, party: str, chamber: str) -> MemberSummary:
    return MemberSummary(
        bioguide_id=member_id,
        display_name=member_id,
        party=party,
        state="X",
        chamber=chamber,
    )


class FakeMembers(MemberService):
    def __init__(self, members: dict[str, MemberSummary]) -> None:
        self.table = members

    def get_summaries(self, bioguide_ids: list[str]) -> dict[str, MemberSummary]:
        return {key: self.table[key] for key in bioguide_ids if key in self.table}


class FakeGraph(GraphService):
    def __init__(self) -> None:
        self.table = {
            Signal.COLLABORATION: [
                _edge(Signal.COLLABORATION, "A", "B", 0.02),
                _edge(Signal.COLLABORATION, "A", "C", 0.01),
            ],
            Signal.VOTING: [
                _edge(Signal.VOTING, "A", "B", 0.9),
                _edge(Signal.VOTING, "A", "C", 0.3),
            ],
        }

    def snapshot(
        self, signals: list[Signal], *, include_topics: bool = False
    ) -> GraphReadSnapshot:
        return GraphReadSnapshot(
            pointers={
                signal: GraphVersionPointer(
                    signal=signal, graph_version="v1", source_model_version="v1"
                )
                for signal in signals
            },
            topic_model_version="v1",
        )

    def edges(self, version, signal, members, congress, size, neighbors=None):
        return [
            edge
            for edge in self.table[signal]
            if edge.member in members
            and (neighbors is None or edge.neighbor in neighbors)
        ]


@pytest.fixture
def service() -> NeighborhoodService:
    members = {
        "A": _summary("A", "Democratic", "House of Representatives"),
        "B": _summary("B", "Democratic", "Senate"),
        "C": _summary("C", "Republican", "House of Representatives"),
    }
    return NeighborhoodService(
        FakeGraph(),
        FakeMembers(members),
        None,
        None,
        None,  # type: ignore[arg-type]
    )


def _query(parties: set[PartyGroup] | None = None) -> NeighborhoodQuery:
    return NeighborhoodQuery(
        seeds=["A"],
        weights={Signal.COLLABORATION: 1.0, Signal.VOTING: 1.0},
        parties=parties or set(),
    )


def test_blends_signals_and_marks_seed(service: NeighborhoodService):
    response = service.neighborhood(_query())
    assert [node.member.bioguide_id for node in response.nodes] == ["A", "B", "C"]
    assert response.nodes[0].is_seed
    best = response.links[0]
    assert (best.source, best.target) == ("A", "B")
    assert best.score > response.links[1].score


def test_party_filter_removes_other_party(service: NeighborhoodService):
    response = service.neighborhood(_query({PartyGroup.DEMOCRATIC}))
    assert {node.member.bioguide_id for node in response.nodes} == {"A", "B"}
    assert all(node.party_group is PartyGroup.DEMOCRATIC for node in response.nodes)


def test_zero_weight_signal_is_ignored(service: NeighborhoodService):
    query = NeighborhoodQuery(
        seeds=["A"], weights={Signal.COLLABORATION: 1.0, Signal.VOTING: 0.0}
    )
    response = service.neighborhood(query)
    assert set(response.versions) == {Signal.COLLABORATION}


def test_shared_topics_are_carried_to_links(service: NeighborhoodService):
    graph = cast(FakeGraph, service.graph)
    graph.table[Signal.TOPIC] = [
        MemberEdge(
            graph_version="v1",
            signal=Signal.TOPIC,
            member="A",
            neighbor="B",
            score=0.6,
            shared_topics=["health care"],
        )
    ]
    query = NeighborhoodQuery(seeds=["A"], weights={Signal.TOPIC: 1.0})
    link = service.neighborhood(query).links[0]
    assert link.shared_topics == ["health care"]


def test_edge_query_size_is_capped_to_result_window() -> None:
    client = Mock()
    client.search.return_value = ObjectApiResponse(
        {"timed_out": False, "_shards": {"failed": 0}, "hits": {"hits": []}}, Mock()
    )
    graph = GraphService(
        GraphStore(client), Mock(spec=MemberService), Mock(spec=TopicPublicationStore)
    )
    graph.edges("v1", Signal.TOPIC, ["A"], None, 50_000, neighbors=["B"])
    assert client.search.call_args.kwargs["size"] == QueryReadConfig().max_result_window

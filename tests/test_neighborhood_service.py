from typing import cast

import pytest

from cdm.backend.services.graph_service import GraphService
from cdm.backend.services.member_service import MemberService
from cdm.backend.services.neighborhood_service import (
    NeighborhoodQuery,
    NeighborhoodService,
)
from cdm.contracts.api import MemberSummary
from cdm.graph.models import MemberEdge, PartyGroup, Signal


def _edge(signal: Signal, member: str, neighbor: str, score: float) -> MemberEdge:
    return MemberEdge(
        graph_version="v1", signal=signal, member=member, neighbor=neighbor, score=score
    )


def _summary(member_id: str, party: str, chamber: str) -> MemberSummary:
    return MemberSummary(
        bioguide_id=member_id, display_name=member_id, party=party, state="X", chamber=chamber
    )


class FakeMembers(MemberService):
    def __init__(self, members: dict[str, MemberSummary]) -> None:
        self.table = members

    def get_summaries(self, bioguide_ids: list[str]) -> dict[str, MemberSummary]:
        return {key: self.table[key] for key in bioguide_ids if key in self.table}


class FakeGraph(GraphService):
    def __init__(self) -> None:
        self.table = {
            Signal.COLLABORATION: [_edge(Signal.COLLABORATION, "A", "B", 0.02), _edge(Signal.COLLABORATION, "A", "C", 0.01)],
            Signal.VOTING: [_edge(Signal.VOTING, "A", "B", 0.9), _edge(Signal.VOTING, "A", "C", 0.3)],
        }

    def active_version(self, signal: Signal) -> str | None:
        return "v1"

    def edges(self, version, signal, members, congress, size, neighbors=None):
        return [
            edge for edge in self.table[signal]
            if edge.member in members and (neighbors is None or edge.neighbor in neighbors)
        ]


@pytest.fixture
def service() -> NeighborhoodService:
    members = {
        "A": _summary("A", "Democratic", "House of Representatives"),
        "B": _summary("B", "Democratic", "Senate"),
        "C": _summary("C", "Republican", "House of Representatives"),
    }
    return NeighborhoodService(
        FakeGraph(), FakeMembers(members), None, None, None  # type: ignore[arg-type]
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
            graph_version="v1", signal=Signal.TOPIC, member="A", neighbor="B",
            score=0.6, shared_topics=["health care"],
        )
    ]
    query = NeighborhoodQuery(seeds=["A"], weights={Signal.TOPIC: 1.0})
    link = service.neighborhood(query).links[0]
    assert link.shared_topics == ["health care"]

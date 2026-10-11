from collections import Counter
from typing import cast

from cdm.backend.services.neighborhood_service import (
    NeighborhoodQuery,
    NeighborhoodService,
)
from cdm.backend.services.topic_neighborhood_service import (
    TopicNeighborhoodQuery,
    TopicNeighborhoodService,
)
from cdm.backend.services.topic_service import TopicService
from cdm.backend.services.topic_sponsors import (
    AssignedBillReader,
    AssignmentField,
    CenterKind,
    TopicSponsorReader,
)
from cdm.contracts.api import GraphLink, MemberSummary
from cdm.graph.models import Signal


def _summary(member_id: str, party: str) -> MemberSummary:
    return MemberSummary(
        bioguide_id=member_id, display_name=member_id, party=party, state="X", chamber="Senate"
    )


class FakeNeighborhoods(NeighborhoodService):
    def __init__(self) -> None:
        self.table = {"A": _summary("A", "Democratic"), "B": _summary("B", "Republican")}

    def allowed_members(self, member_ids: list[str], query: NeighborhoodQuery) -> dict[str, MemberSummary]:
        return {key: self.table[key] for key in member_ids if key in self.table}

    def links_among(self, member_ids, query):  # type: ignore[no-untyped-def]
        return {Signal.COLLABORATION: "v1"}, [GraphLink(source="A", target="B", score=0.5)]


class FakeTopics:
    def latest_model_version(self) -> tuple[str | None, str | None]:
        return "v1", None

    def topic_summaries(self, version: str) -> dict[int, object]:
        return {}

    def metasubject_summaries(self, version: str) -> dict[int, object]:
        return {}


class FakeAssigned:
    def read(self, field: AssignmentField, value: int, version: str) -> list[str]:
        return ["b1", "b2"]


class FakeSponsors:
    def by_bill_ids(self, bill_ids, congress):  # type: ignore[no-untyped-def]
        return Counter({"A": 5, "B": 2, "C": 1, "D": 9})

    def by_subject(self, subject: str, congress: int | None) -> Counter[str]:
        return Counter({"A": 3})


def _service() -> TopicNeighborhoodService:
    return TopicNeighborhoodService(
        FakeNeighborhoods(),
        cast(TopicService, FakeTopics()),
        cast(AssignedBillReader, FakeAssigned()),
        cast(TopicSponsorReader, FakeSponsors()),
    )


def _query(kind: CenterKind, key: str) -> TopicNeighborhoodQuery:
    return TopicNeighborhoodQuery(
        kind=kind,
        key=key,
        neighborhood=NeighborhoodQuery(seeds=[], weights={Signal.COLLABORATION: 1.0}),
    )


def test_topic_center_ranks_sponsors_and_drops_unknown_members() -> None:
    response = _service().neighborhood(_query(CenterKind.TOPIC, "7"))
    assert [node.member.bioguide_id for node in response.nodes] == ["A", "B"]
    assert response.topic_nodes[0].topic_id == 7
    assert {link.member: link.bills for link in response.topic_links} == {"A": 5, "B": 2}
    assert len(response.links) == 1


def test_subject_center_requires_min_bills() -> None:
    response = _service().neighborhood(_query(CenterKind.SUBJECT, "Health"))
    assert [node.member.bioguide_id for node in response.nodes] == ["A"]
    assert response.subject_nodes[0].name == "Health"


def test_unknown_topic_key_returns_empty() -> None:
    response = _service().neighborhood(_query(CenterKind.METASUBJECT, "x"))
    assert response.nodes == []

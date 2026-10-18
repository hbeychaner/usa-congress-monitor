from unittest.mock import MagicMock

from elasticsearch import Elasticsearch

from cdm.backend.services.party_service import PartyService
from cdm.config import PerspectiveConfig
from cdm.graph.models import PartyGroup
from cdm.perspectives.models import (
    BilateralSupport,
    PartyBillCount,
    PartyTerms,
    Perspective,
    TopicPerspectives,
)
from cdm.store.perspective_repository import PerspectiveRepository

CONGRESS = 119
VERSION = "v1"


class FakeRepository(PerspectiveRepository):
    def __init__(self, topics: list[TopicPerspectives]) -> None:
        self.topics = topics

    def congresses(self) -> list[int]:
        return [CONGRESS] if self.topics else []

    def read(self, congress: int) -> tuple[list[TopicPerspectives], str | None]:
        return (self.topics, VERSION) if self.topics else ([], None)


def _topic(
    topic_id: int, dem: int, rep: int, *, bilateral: bool = False
) -> TopicPerspectives:
    return TopicPerspectives(
        congress=CONGRESS,
        topic_id=topic_id,
        topic_label=f"topic {topic_id}",
        bills=dem + rep,
        party_bills=[
            PartyBillCount(party=PartyGroup.DEMOCRATIC, bills=dem),
            PartyBillCount(party=PartyGroup.REPUBLICAN, bills=rep),
            PartyBillCount(party=PartyGroup.OTHER, bills=0),
        ],
        party_terms=[
            PartyTerms(
                party=PartyGroup.DEMOCRATIC,
                bills=dem,
                terms=["a b"],
                summary="dem view",
            )
        ],
        bilateral=BilateralSupport(
            bills=dem + rep,
            bipartisan_bills=5,
            share=0.3,
            bilateral=bilateral,
            terms=["x y"],
        ),
        perspectives=[
            Perspective(
                congress=CONGRESS,
                topic_id=topic_id,
                perspective_id=0,
                label="p",
                size=3,
            )
        ],
    )


def _service(topics: list[TopicPerspectives]) -> PartyService:
    return PartyService(FakeRepository(topics), PerspectiveConfig())


def test_overview_ranks_topics_by_each_partys_bills() -> None:
    response = _service([_topic(1, 30, 5), _topic(2, 10, 40)]).overview(None)

    democratic, republican = response.parties
    assert response.congress == CONGRESS
    assert [entry.topic_id for entry in democratic.topics] == [1, 2]
    assert [entry.topic_id for entry in republican.topics] == [2, 1]
    assert democratic.topics[0].share_of_topic == 30 / 35
    assert democratic.topics[0].summary == "dem view"


def test_overview_lists_only_bilateral_topics() -> None:
    response = _service([_topic(1, 30, 5, bilateral=True), _topic(2, 10, 40)]).overview(
        CONGRESS
    )

    assert [entry.topic_id for entry in response.bilateral] == [1]


def test_overview_is_empty_without_stored_analysis() -> None:
    response = _service([]).overview(None)

    assert response.congress is None
    assert response.parties == []


def test_topic_hides_clusters_that_failed_the_gate() -> None:
    result = _service([_topic(1, 30, 5)]).topic(CONGRESS, 1)

    assert result is not None
    assert result.topic.perspectives == []
    assert _service([_topic(1, 30, 5)]).topic(CONGRESS, 99) is None


def test_repository_actions_carry_version_and_identity() -> None:
    repository = PerspectiveRepository(MagicMock(spec=Elasticsearch), "analysis")

    actions = list(
        repository.actions(VERSION, "2026-01-01T00:00:00+00:00", [_topic(7, 1, 1)])
    )

    assert actions[0]["_id"] == f"party_topic:{VERSION}:{CONGRESS}:7"
    assert actions[0]["kind"] == "party_topic"
    assert actions[0]["topic_id"] == 7

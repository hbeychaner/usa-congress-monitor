import pytest

from cdm.backend.services.member_topic_overlay import MemberTopicOverlayBuilder
from cdm.backend.services.sponsored_bills import SponsoredBillReader
from cdm.backend.services.topic_service import TopicService
from cdm.contracts.api import TopicSummary


def _summary(topic_id: int, label: str) -> TopicSummary:
    return TopicSummary(topic_id=topic_id, name="", label=label, size=1, top_words=[])


class FakeTopics(TopicService):
    def __init__(self) -> None:
        pass

    def latest_model_version(self) -> tuple[str | None, str | None]:
        return "v1", None

    def member_assignments(self, bill_ids: list[str], model_version: str) -> list[tuple[str, int]]:
        return [("b1", 1), ("b2", 1), ("b3", 2), ("b4", 1), ("b5", 2)]

    def topic_summaries(self, model_version: str) -> dict[int, TopicSummary]:
        return {1: _summary(1, "health")}


def test_overlay_links_top_topics_with_min_bills(monkeypatch: pytest.MonkeyPatch) -> None:
    reader = SponsoredBillReader(object())  # type: ignore[arg-type]
    monkeypatch.setattr(reader, "by_member", lambda ids, congress: {"A": ["b1", "b2", "b3", "b4"], "B": ["b5"]})
    builder = MemberTopicOverlayBuilder(reader, FakeTopics())

    overlay = builder.build(["A", "B"], None, 3)

    assert [(link.member, link.topic_id, link.bills) for link in overlay.links] == [("A", 1, 3)]
    assert [(node.topic_id, node.label) for node in overlay.nodes] == [(1, "health")]

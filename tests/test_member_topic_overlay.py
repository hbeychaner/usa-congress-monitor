import pytest

from cdm.backend.services import member_topic_overlay as overlay_module
from cdm.backend.services.member_topic_overlay import MemberTopicOverlayBuilder
from cdm.contracts.api import TopicSummary


def _summary(topic_id: int, label: str) -> TopicSummary:
    return TopicSummary(topic_id=topic_id, name="", label=label, size=1, top_words=[])


def test_overlay_links_top_topics_with_min_bills(monkeypatch: pytest.MonkeyPatch) -> None:
    builder = MemberTopicOverlayBuilder(client=object())  # type: ignore[arg-type]
    monkeypatch.setattr(builder, "_sponsored_bills", lambda ids, congress: {"A": ["b1", "b2", "b3", "b4"], "B": ["b5"]})
    topics = overlay_module.topic_service
    monkeypatch.setattr(topics, "_latest_model_version", lambda: ("v1", None))
    monkeypatch.setattr(
        topics, "_member_assignments", lambda bills, version: [("b1", 1), ("b2", 1), ("b3", 2), ("b4", 1), ("b5", 2)]
    )
    monkeypatch.setattr(topics, "_topic_summaries", lambda version: {1: _summary(1, "health")})

    overlay = builder.build(["A", "B"], None, 3)

    assert [(link.member, link.topic_id, link.bills) for link in overlay.links] == [("A", 1, 3)]
    assert [(node.topic_id, node.label) for node in overlay.nodes] == [(1, "health")]

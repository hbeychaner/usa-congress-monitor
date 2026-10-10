"""Topic nodes for the member graph: each member's dominant sponsored-bill topics."""

from __future__ import annotations

from collections import Counter

from cdm.backend.services.sponsored_bills import SponsoredBillReader
from cdm.backend.services.topic_service import TopicService
from cdm.contracts.api import GraphTopicLink, GraphTopicNode

MIN_BILLS = 2


class TopicOverlay:
    def __init__(self, nodes: list[GraphTopicNode], links: list[GraphTopicLink]) -> None:
        self.nodes = nodes
        self.links = links


class MemberTopicOverlayBuilder:
    def __init__(self, bills: SponsoredBillReader, topics: TopicService) -> None:
        self.bills = bills
        self.topics = topics

    def build(self, member_ids: list[str], congress: int | None, per_member: int) -> TopicOverlay:
        version, _ = self.topics.latest_model_version()
        if not version or not member_ids:
            return TopicOverlay([], [])
        bills = self.bills.by_member(member_ids, congress)
        all_bills = sorted({bill for ids in bills.values() for bill in ids})
        topic_of = dict(self.topics.member_assignments(all_bills, version))
        links: list[GraphTopicLink] = []
        for member, ids in bills.items():
            counts = Counter(topic_of[bill] for bill in ids if bill in topic_of)
            total = sum(counts.values())
            for topic_id, count in counts.most_common(per_member):
                if count >= MIN_BILLS:
                    links.append(
                        GraphTopicLink(member=member, topic_id=topic_id, share=count / total, bills=count)
                    )
        summaries = self.topics.topic_summaries(version)
        topic_ids = sorted({link.topic_id for link in links})
        nodes = [
            GraphTopicNode(
                topic_id=topic_id,
                label=summaries[topic_id].label if topic_id in summaries else f"Topic {topic_id}",
            )
            for topic_id in topic_ids
        ]
        return TopicOverlay(nodes, links)

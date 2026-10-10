"""Metasubject nodes for the member graph: each member's dominant sponsored-bill metasubjects."""

from __future__ import annotations

from collections import Counter

from cdm.backend.services.member_topic_overlay import MIN_BILLS
from cdm.backend.services.sponsored_bills import SponsoredBillReader
from cdm.backend.services.topic_service import TopicService
from cdm.contracts.api import GraphMetasubjectLink, GraphMetasubjectNode


class MetasubjectOverlay:
    def __init__(
        self, nodes: list[GraphMetasubjectNode], links: list[GraphMetasubjectLink]
    ) -> None:
        self.nodes = nodes
        self.links = links


class MemberMetasubjectOverlayBuilder:
    def __init__(self, bills: SponsoredBillReader, topics: TopicService) -> None:
        self.bills = bills
        self.topics = topics

    def build(self, member_ids: list[str], congress: int | None, per_member: int) -> MetasubjectOverlay:
        version, _ = self.topics.latest_model_version()
        if not version or not member_ids:
            return MetasubjectOverlay([], [])
        bills = self.bills.by_member(member_ids, congress)
        all_bills = sorted({bill for ids in bills.values() for bill in ids})
        group_of = dict(self.topics.member_metasubject_assignments(all_bills, version))
        links: list[GraphMetasubjectLink] = []
        for member, ids in bills.items():
            counts = Counter(group_of[bill] for bill in ids if bill in group_of)
            total = sum(counts.values())
            for metasubject_id, count in counts.most_common(per_member):
                if count >= MIN_BILLS:
                    links.append(
                        GraphMetasubjectLink(
                            member=member, metasubject_id=metasubject_id, share=count / total, bills=count
                        )
                    )
        summaries = self.topics.metasubject_summaries(version)
        nodes = [
            GraphMetasubjectNode(
                metasubject_id=metasubject_id,
                name=summaries[metasubject_id].name if metasubject_id in summaries else f"Group {metasubject_id}",
            )
            for metasubject_id in sorted({link.metasubject_id for link in links})
        ]
        return MetasubjectOverlay(nodes, links)

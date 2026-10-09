"""Topic nodes for the member graph: each member's dominant sponsored-bill topics."""

from __future__ import annotations

from collections import Counter

from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch.helpers import scan

from cdm.backend.services import topic_service
from cdm.contracts.api import GraphTopicLink, GraphTopicNode
from cdm.store.client import get_opensearch_client
from cdm.store.opensearch import read_alias

SPONSOR_FIELD = "sponsor_bioguide_ids"
MIN_BILLS = 2


class TopicOverlay:
    def __init__(self, nodes: list[GraphTopicNode], links: list[GraphTopicLink]) -> None:
        self.nodes = nodes
        self.links = links


class MemberTopicOverlayBuilder:
    def __init__(self, client: Elasticsearch | None = None) -> None:
        self.client = client or get_opensearch_client()

    def _sponsored_bills(self, member_ids: list[str], congress: int | None) -> dict[str, list[str]]:
        filters: list[dict[str, object]] = [
            {"term": {"source_type": "bill"}},
            {"terms": {SPONSOR_FIELD: member_ids}},
        ]
        if congress:
            filters.append({"term": {"congress": congress}})
        bills: dict[str, list[str]] = {}
        try:
            for hit in scan(
                self.client,
                index=read_alias("bill"),
                query={"query": {"bool": {"filter": filters}}, "_source": [SPONSOR_FIELD]},
            ):
                for sponsor in hit["_source"].get(SPONSOR_FIELD) or []:
                    if sponsor in member_ids:
                        bills.setdefault(sponsor, []).append(hit["_id"])
        except NotFoundError:
            return {}
        return bills

    def build(self, member_ids: list[str], congress: int | None, per_member: int) -> TopicOverlay:
        version, _ = topic_service._latest_model_version()
        if not version or not member_ids:
            return TopicOverlay([], [])
        bills = self._sponsored_bills(member_ids, congress)
        all_bills = sorted({bill for ids in bills.values() for bill in ids})
        topic_of = dict(topic_service._member_assignments(all_bills, version))
        links: list[GraphTopicLink] = []
        for member, ids in bills.items():
            counts = Counter(topic_of[bill] for bill in ids if bill in topic_of)
            total = sum(counts.values())
            for topic_id, count in counts.most_common(per_member):
                if count >= MIN_BILLS:
                    links.append(
                        GraphTopicLink(member=member, topic_id=topic_id, share=count / total, bills=count)
                    )
        summaries = topic_service._topic_summaries(version)
        topic_ids = sorted({link.topic_id for link in links})
        nodes = [
            GraphTopicNode(
                topic_id=topic_id,
                label=summaries[topic_id].label if topic_id in summaries else f"Topic {topic_id}",
            )
            for topic_id in topic_ids
        ]
        return TopicOverlay(nodes, links)

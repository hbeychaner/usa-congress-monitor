"""Subject nodes for the member graph: each member's dominant CRS subjects on sponsored bills."""

from __future__ import annotations

from elasticsearch import Elasticsearch, NotFoundError

from cdm.backend.services.member_topic_overlay import MIN_BILLS, SPONSOR_FIELD
from cdm.contracts.api import GraphSubjectLink, GraphSubjectNode
from cdm.store.opensearch import read_alias

SUBJECTS_PATH = "subjects.legislative_subjects"
SUBJECT_FIELD = f"{SUBJECTS_PATH}.name"
PER_MEMBER_BUCKETS = 50


class SubjectOverlay:
    def __init__(self, nodes: list[GraphSubjectNode], links: list[GraphSubjectLink]) -> None:
        self.nodes = nodes
        self.links = links


class MemberSubjectOverlayBuilder:
    def __init__(self, client: Elasticsearch) -> None:
        self.client = client

    def _search(self, member_ids: list[str], congress: int | None) -> dict[str, object]:
        filters: list[dict[str, object]] = [
            {"term": {"source_type": "bill"}},
            {"terms": {SPONSOR_FIELD: member_ids}},
        ]
        if congress:
            filters.append({"term": {"congress": congress}})
        aggs = {
            "members": {
                "terms": {"field": SPONSOR_FIELD, "include": member_ids, "size": len(member_ids)},
                "aggs": {
                    "subjects": {
                        "nested": {"path": SUBJECTS_PATH},
                        "aggs": {"names": {"terms": {"field": SUBJECT_FIELD, "size": PER_MEMBER_BUCKETS}}},
                    }
                },
            }
        }
        try:
            return self.client.search(
                index=read_alias("bill"),
                body={"size": 0, "query": {"bool": {"filter": filters}}, "aggs": aggs},
            ).body
        except NotFoundError:
            return {}

    def build(self, member_ids: list[str], congress: int | None, per_member: int) -> SubjectOverlay:
        if not member_ids:
            return SubjectOverlay([], [])
        response = self._search(member_ids, congress)
        links: list[GraphSubjectLink] = []
        for member in response.get("aggregations", {}).get("members", {}).get("buckets", []):
            names = member["subjects"]["names"]["buckets"]
            for bucket in names[:per_member]:
                if bucket["doc_count"] >= MIN_BILLS:
                    links.append(
                        GraphSubjectLink(member=str(member["key"]), subject=str(bucket["key"]), bills=int(bucket["doc_count"]))
                    )
        nodes = [GraphSubjectNode(name=name) for name in sorted({link.subject for link in links})]
        return SubjectOverlay(nodes, links)

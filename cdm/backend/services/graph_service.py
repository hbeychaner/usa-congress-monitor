"""Read precomputed member-graph edges for API responses."""

from __future__ import annotations

from elasticsearch import Elasticsearch

from cdm.backend.services.member_service import get_member_summaries
from cdm.contracts.api import SimilarMember, SimilarMembersResponse
from cdm.graph.models import (
    CongressEdgeStats,
    DocumentKind,
    GraphField,
    MemberEdge,
    Signal,
)
from cdm.graph.store import GraphStore
from cdm.store.client import get_opensearch_client


class GraphService:
    """Answers similar-member queries from the live graph version."""

    def __init__(self, client: Elasticsearch | None = None) -> None:
        self._client = client

    @property
    def client(self) -> Elasticsearch:
        if self._client is None:
            self._client = get_opensearch_client()
        return self._client

    def similar(
        self, bioguide_id: str, signal: Signal, congress: int | None, limit: int
    ) -> SimilarMembersResponse:
        store = GraphStore(self.client)
        version = store.active_version(signal)
        if version is None:
            return SimilarMembersResponse(
                member_id=bioguide_id, signal=signal, congress=congress, similar=[]
            )
        edges = self._edges(store, version, bioguide_id, signal, congress, limit)
        members = get_member_summaries([edge.neighbor for edge in edges])
        similar = [
            SimilarMember(
                member=members[edge.neighbor],
                **self._stats(edge, congress),
            )
            for edge in edges
            if edge.neighbor in members
        ]
        return SimilarMembersResponse(
            member_id=bioguide_id,
            signal=signal,
            congress=congress,
            graph_version=version,
            similar=similar,
        )

    def _edges(
        self,
        store: GraphStore,
        version: str,
        bioguide_id: str,
        signal: Signal,
        congress: int | None,
        limit: int,
    ) -> list[MemberEdge]:
        filters: list[dict] = [
            {"term": {GraphField.KIND: DocumentKind.EDGE}},
            {"term": {GraphField.SIGNAL: signal}},
            {"term": {GraphField.GRAPH_VERSION: version}},
            {"term": {GraphField.MEMBER: bioguide_id}},
        ]
        congress_filter = (
            {"term": {GraphField.BY_CONGRESS_CONGRESS: congress}}
            if congress is not None
            else None
        )
        if congress_filter:
            filters.append({
                "nested": {
                    "path": GraphField.BY_CONGRESS,
                    "query": congress_filter,
                }
            })
            sort: dict = {
                GraphField.BY_CONGRESS_SCORE: {
                    "order": "desc",
                    "nested": {
                        "path": GraphField.BY_CONGRESS,
                        "filter": congress_filter,
                    },
                }
            }
        else:
            sort = {GraphField.SCORE: {"order": "desc"}}
        response = self.client.search(
            index=store.index,
            size=limit,
            query={"bool": {"filter": filters}},
            sort=[sort],
        )
        return [
            MemberEdge.model_validate(hit["_source"]) for hit in response["hits"]["hits"]
        ]

    @staticmethod
    def _stats(edge: MemberEdge, congress: int | None) -> dict[str, float | int]:
        selected: list[CongressEdgeStats] = [
            stats
            for stats in edge.by_congress
            if congress is None or stats.congress == congress
        ]
        return {
            "score": (
                selected[0].score
                if congress is not None and selected
                else edge.score
            ),
            "member_sponsored": sum(stats.member_sponsored for stats in selected),
            "neighbor_sponsored": sum(stats.neighbor_sponsored for stats in selected),
            "co_signed": sum(stats.co_signed for stats in selected),
            "shared_votes": sum(stats.shared_votes for stats in selected),
            "agreed_votes": sum(stats.agreed_votes for stats in selected),
            "shared_split_votes": sum(stats.shared_split_votes for stats in selected),
            "agreed_split_votes": sum(stats.agreed_split_votes for stats in selected),
        }

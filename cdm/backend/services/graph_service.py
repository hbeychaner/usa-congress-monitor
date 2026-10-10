"""Read precomputed member-graph edges for API responses."""

from __future__ import annotations

from typing import Any

from elasticsearch import Elasticsearch

from cdm.backend.services.member_service import MemberService
from cdm.contracts.api import MemberSummary, SimilarMember, SimilarMembersResponse
from cdm.graph.models import (
    CongressEdgeStats,
    DocumentKind,
    GraphField,
    MemberEdge,
    Signal,
)
from cdm.graph.store import GraphStore


class GraphService:
    """Answers edge queries against the live graph version of each signal."""

    def __init__(self, client: Elasticsearch, members: MemberService) -> None:
        self.client = client
        self._members = members

    @property
    def store(self) -> GraphStore:
        return GraphStore(self.client)

    def active_version(self, signal: Signal) -> str | None:
        return self.store.active_version(signal)

    def edges(
        self,
        version: str,
        signal: Signal,
        members: list[str],
        congress: int | None,
        size: int,
        neighbors: list[str] | None = None,
    ) -> list[MemberEdge]:
        """Edges from the members (optionally only to the neighbors), best first."""
        filters: list[dict[str, Any]] = [
            {"term": {GraphField.KIND: DocumentKind.EDGE}},
            {"term": {GraphField.SIGNAL: signal}},
            {"term": {GraphField.GRAPH_VERSION: version}},
            {"terms": {GraphField.MEMBER: members}},
        ]
        if neighbors is not None:
            filters.append({"terms": {GraphField.NEIGHBOR: neighbors}})
        if congress is None:
            sort: dict[str, Any] = {GraphField.SCORE: {"order": "desc"}}
        else:
            congress_filter = {"term": {GraphField.BY_CONGRESS_CONGRESS: congress}}
            filters.append({
                "nested": {"path": GraphField.BY_CONGRESS, "query": congress_filter}
            })
            sort = {
                GraphField.BY_CONGRESS_SCORE: {
                    "order": "desc",
                    "nested": {
                        "path": GraphField.BY_CONGRESS,
                        "filter": congress_filter,
                    },
                }
            }
        response = self.client.search(
            index=self.store.index,
            size=size,
            query={"bool": {"filter": filters}},
            sort=[sort],
        )
        return [
            MemberEdge.model_validate(hit["_source"])
            for hit in response["hits"]["hits"]
        ]

    @staticmethod
    def score(edge: MemberEdge, congress: int | None) -> float:
        if congress is None:
            return edge.score
        return next(
            (stats.score for stats in edge.by_congress if stats.congress == congress),
            0.0,
        )

    def similar(
        self, bioguide_id: str, signal: Signal, congress: int | None, limit: int
    ) -> SimilarMembersResponse:
        version = self.active_version(signal)
        if version is None:
            return SimilarMembersResponse(
                member_id=bioguide_id, signal=signal, congress=congress, similar=[]
            )
        edges = self.edges(version, signal, [bioguide_id], congress, limit)
        members = self._members.get_summaries([edge.neighbor for edge in edges])
        similar = [
            self._similar_member(members[edge.neighbor], edge, congress)
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

    def _similar_member(
        self, member: MemberSummary, edge: MemberEdge, congress: int | None
    ) -> SimilarMember:
        selected: list[CongressEdgeStats] = [
            stats
            for stats in edge.by_congress
            if congress is None or stats.congress == congress
        ]
        return SimilarMember(
            member=member,
            score=self.score(edge, congress),
            member_sponsored=sum(stats.member_sponsored for stats in selected),
            neighbor_sponsored=sum(stats.neighbor_sponsored for stats in selected),
            co_signed=sum(stats.co_signed for stats in selected),
            shared_votes=sum(stats.shared_votes for stats in selected),
            agreed_votes=sum(stats.agreed_votes for stats in selected),
            shared_split_votes=sum(stats.shared_split_votes for stats in selected),
            agreed_split_votes=sum(stats.agreed_split_votes for stats in selected),
            shared_topics=edge.shared_topics,
        )

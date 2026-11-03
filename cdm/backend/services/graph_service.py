"""Read precomputed member-graph edges for API responses."""

from __future__ import annotations

from pydantic import BaseModel

from cdm.backend.services.member_service import MemberService
from cdm.config.query_reads import QueryReadConfig
from cdm.contracts.analysis import AnalysisState, AnalysisStatus
from cdm.contracts.api import MemberSummary, SimilarMember, SimilarMembersResponse
from cdm.graph.models import (
    CongressEdgeStats,
    DocumentKind,
    GraphField,
    GraphVersionPointer,
    MemberEdge,
    Signal,
)
from cdm.graph.store import GraphStore
from cdm.store.client import SearchCompletion
from cdm.store.topic_publication import TopicPublicationStore
from cdm.utils.json_types import JsonObject


class GraphReadSnapshot(BaseModel):
    pointers: dict[Signal, GraphVersionPointer | None]
    topic_model_version: str | None

    @property
    def versions(self) -> dict[Signal, str]:
        return {
            signal: pointer.graph_version
            for signal, pointer in self.pointers.items()
            if pointer is not None
        }

    def analysis(
        self, with_results: set[Signal], congress: int | None = None
    ) -> dict[Signal, AnalysisStatus]:
        statuses: dict[Signal, AnalysisStatus] = {}
        for signal, pointer in self.pointers.items():
            if pointer is None or (
                congress is not None
                and pointer.congresses is not None
                and congress not in pointer.congresses
            ):
                status = AnalysisStatus(
                    state=AnalysisState.NOT_BUILT,
                    published_model_version=self.topic_model_version
                    if signal is Signal.TOPIC
                    else None,
                )
            elif signal is Signal.TOPIC:
                status = AnalysisStatus.for_model(
                    pointer.source_model_version,
                    self.topic_model_version,
                    signal in with_results,
                )
                if pointer.source_model_version is None:
                    status.state = AnalysisState.UNKNOWN
            else:
                status = AnalysisStatus(
                    state=AnalysisState.AVAILABLE
                    if signal in with_results
                    else AnalysisState.EMPTY
                )
            if (
                pointer is not None
                and pointer.congresses is None
                and signal not in with_results
                and status.state is AnalysisState.EMPTY
            ):
                status.state = AnalysisState.UNKNOWN
            statuses[signal] = status
        return statuses


class GraphService:
    """Answers edge queries against the live graph version of each signal."""

    def __init__(
        self,
        store: GraphStore,
        members: MemberService,
        publications: TopicPublicationStore,
        reads: QueryReadConfig | None = None,
    ) -> None:
        self.store = store
        self.client = store.client
        self._members = members
        self._publications = publications
        self._reads = reads or QueryReadConfig()

    def snapshot(
        self, signals: list[Signal], *, include_topics: bool = False
    ) -> GraphReadSnapshot:
        run = (
            self._publications.current()
            if Signal.TOPIC in signals or include_topics
            else None
        )
        return GraphReadSnapshot(
            pointers={signal: self.store.active_pointer(signal) for signal in signals},
            topic_model_version=run.model_version if run else None,
        )

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
        filters: list[JsonObject] = [
            {"term": {GraphField.KIND: DocumentKind.EDGE}},
            {"term": {GraphField.SIGNAL: signal}},
            {"term": {GraphField.GRAPH_VERSION: version}},
            {"terms": {GraphField.MEMBER: members}},
        ]
        if neighbors is not None:
            filters.append({"terms": {GraphField.NEIGHBOR: neighbors}})
        if congress is None:
            sort: JsonObject = {GraphField.SCORE: {"order": "desc"}}
        else:
            congress_filter: JsonObject = {
                "term": {GraphField.BY_CONGRESS_CONGRESS: congress}
            }
            filters.append(
                {"nested": {"path": GraphField.BY_CONGRESS, "query": congress_filter}}
            )
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
            allow_partial_search_results=False,
            size=min(size, self._reads.max_result_window),
            query={"bool": {"filter": filters}},
            sort=[sort],
        )
        SearchCompletion.model_validate(response.body).require_complete()
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
        snapshot = self.snapshot([signal])
        version = snapshot.versions.get(signal)
        if version is None:
            return SimilarMembersResponse(
                member_id=bioguide_id,
                signal=signal,
                congress=congress,
                similar=[],
                analysis=snapshot.analysis(set(), congress)[signal],
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
            analysis=snapshot.analysis({signal} if similar else set(), congress)[
                signal
            ],
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

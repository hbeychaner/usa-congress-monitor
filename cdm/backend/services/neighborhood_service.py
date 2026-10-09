"""Blend graph signals into a filtered neighborhood of nodes and links."""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel, Field

from cdm.backend.services.graph_service import GraphService
from cdm.backend.services.member_service import get_member_summaries
from cdm.backend.services.member_subject_overlay import MemberSubjectOverlayBuilder
from cdm.backend.services.member_topic_overlay import MemberTopicOverlayBuilder
from cdm.contracts.api import (
    GraphLink,
    GraphNode,
    MemberSummary,
    NeighborhoodResponse,
)
from cdm.graph.models import MemberEdge, PartyGroup, Signal
from cdm.ingest.voteview import Chamber

CANDIDATE_FACTOR = 3
VOTING_FLOOR = 0.5
TOPIC_FLOOR = 0.2

PairKey = tuple[str, str]


class NeighborhoodQuery(BaseModel):
    seeds: list[str]
    weights: dict[Signal, float]
    congress: int | None = None
    limit: int = 15
    parties: set[PartyGroup] = Field(default_factory=set)
    chamber: Chamber | None = None
    include_topics: bool = False
    topics_per_member: int = 3
    include_subjects: bool = False
    subjects_per_member: int = 3

    @property
    def signals(self) -> list[Signal]:
        return [signal for signal, weight in self.weights.items() if weight > 0]


class SignalScaler:
    """Maps raw signal scores to 0..1 so signals with different scales can blend."""

    def __init__(self) -> None:
        self.collaboration_max = 0.0

    def fit(self, signal: Signal, scores: list[float]) -> None:
        if signal is Signal.COLLABORATION and scores:
            self.collaboration_max = max(scores)

    def apply(self, signal: Signal, score: float) -> float:
        if signal is Signal.VOTING:
            return max(0.0, (score - VOTING_FLOOR) / (1 - VOTING_FLOOR))
        if signal is Signal.TOPIC:
            return max(0.0, (score - TOPIC_FLOOR) / (1 - TOPIC_FLOOR))
        if self.collaboration_max <= 0:
            return 0.0
        return min(1.0, score / self.collaboration_max)


class NeighborhoodService:
    def __init__(self, graph: GraphService | None = None) -> None:
        self.graph = graph or GraphService()

    @staticmethod
    def _key(first: str, second: str) -> PairKey:
        return (first, second) if first < second else (second, first)

    @staticmethod
    def _chamber_of(member: MemberSummary) -> Chamber | None:
        name = (member.chamber or "").lower()
        if "senate" in name:
            return Chamber.SENATE
        if "house" in name:
            return Chamber.HOUSE
        return None

    def _allowed(self, member: MemberSummary, query: NeighborhoodQuery) -> bool:
        if query.parties and PartyGroup.of(member.party) not in query.parties:
            return False
        return query.chamber is None or self._chamber_of(member) is query.chamber

    def _collect(
        self,
        pairs: dict[PairKey, dict[Signal, float]],
        edges: list[MemberEdge],
        signal: Signal,
        scaler: SignalScaler,
        congress: int | None,
        topics: dict[PairKey, list[str]],
    ) -> None:
        for edge in edges:
            key = self._key(edge.member, edge.neighbor)
            score = scaler.apply(signal, self.graph.score(edge, congress))
            pairs[key][signal] = max(pairs[key].get(signal, 0.0), score)
            if edge.shared_topics:
                topics[key] = edge.shared_topics

    @staticmethod
    def _blend(signal_scores: dict[Signal, float], query: NeighborhoodQuery) -> float:
        total = sum(query.weights[signal] for signal in query.signals)
        if total <= 0:
            return 0.0
        return sum(
            query.weights[signal] * signal_scores.get(signal, 0.0)
            for signal in query.signals
        ) / total

    def neighborhood(self, query: NeighborhoodQuery) -> NeighborhoodResponse:
        versions = {
            signal: version
            for signal in query.signals
            if (version := self.graph.active_version(signal)) is not None
        }
        if not versions:
            return NeighborhoodResponse(seeds=query.seeds, congress=query.congress)

        scaler = SignalScaler()
        seed_edges: dict[Signal, list[MemberEdge]] = {}
        for signal, version in versions.items():
            seed_edges[signal] = self.graph.edges(
                version, signal, query.seeds, query.congress,
                query.limit * CANDIDATE_FACTOR * len(query.seeds),
            )
            scaler.fit(signal, [
                self.graph.score(edge, query.congress) for edge in seed_edges[signal]
            ])

        pairs: dict[PairKey, dict[Signal, float]] = defaultdict(dict)
        topics: dict[PairKey, list[str]] = {}
        for signal, edges in seed_edges.items():
            self._collect(pairs, edges, signal, scaler, query.congress, topics)

        seeds = set(query.seeds)
        candidates: dict[str, dict[str, float]] = {seed: {} for seed in query.seeds}
        for (first, second), signal_scores in pairs.items():
            blended = self._blend(signal_scores, query)
            for seed, other in ((first, second), (second, first)):
                if seed in seeds and other not in seeds:
                    candidates[seed][other] = blended

        summaries = get_member_summaries(
            query.seeds + sorted({other for ranked in candidates.values() for other in ranked})
        )
        kept: list[str] = []
        for ranked in candidates.values():
            ordered = sorted(ranked, key=ranked.__getitem__, reverse=True)
            eligible = [
                other for other in ordered
                if other in summaries and self._allowed(summaries[other], query)
            ]
            kept.extend(other for other in eligible[: query.limit] if other not in kept)

        node_ids = [seed for seed in query.seeds if seed in summaries] + kept
        for signal, version in versions.items():
            self._collect(
                pairs,
                self.graph.edges(
                    version, signal, kept, query.congress,
                    max(1, len(kept) * len(node_ids)), neighbors=node_ids,
                ),
                signal,
                scaler,
                query.congress,
                topics,
            )

        node_set = set(node_ids)
        links = [
            GraphLink(
                source=first,
                target=second,
                score=blended,
                signal_scores=signal_scores,
                shared_topics=topics.get((first, second), []),
            )
            for (first, second), signal_scores in pairs.items()
            if first in node_set
            and second in node_set
            and (blended := self._blend(signal_scores, query)) > 0
        ]
        links.sort(key=lambda link: link.score, reverse=True)
        overlay = (
            MemberTopicOverlayBuilder().build(node_ids, query.congress, query.topics_per_member)
            if query.include_topics
            else None
        )
        subjects = (
            MemberSubjectOverlayBuilder().build(node_ids, query.congress, query.subjects_per_member)
            if query.include_subjects
            else None
        )
        return NeighborhoodResponse(
            seeds=query.seeds,
            congress=query.congress,
            versions=versions,
            nodes=[
                GraphNode(
                    member=summaries[member_id],
                    party_group=PartyGroup.of(summaries[member_id].party),
                    is_seed=member_id in seeds,
                )
                for member_id in node_ids
            ],
            links=links,
            topic_nodes=overlay.nodes if overlay else [],
            topic_links=overlay.links if overlay else [],
            subject_nodes=subjects.nodes if subjects else [],
            subject_links=subjects.links if subjects else [],
        )

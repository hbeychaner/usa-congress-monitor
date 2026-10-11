"""Graph centered on one topic, metasubject or subject: the members who sponsor most in it."""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel

from cdm.backend.services.neighborhood_service import (
    NeighborhoodQuery,
    NeighborhoodService,
)
from cdm.backend.services.topic_service import TopicService
from cdm.backend.services.topic_sponsors import (
    AssignedBillReader,
    AssignmentField,
    CenterKind,
    TopicSponsorReader,
)
from cdm.contracts.api import (
    GraphMetasubjectLink,
    GraphMetasubjectNode,
    GraphNode,
    GraphSubjectLink,
    GraphSubjectNode,
    GraphTopicLink,
    GraphTopicNode,
    NeighborhoodResponse,
)
from cdm.graph.models import PartyGroup

MIN_BILLS = 2
CANDIDATE_FACTOR = 3


class TopicNeighborhoodQuery(BaseModel):
    kind: CenterKind
    key: str
    neighborhood: NeighborhoodQuery


class TopicNeighborhoodService:
    def __init__(
        self,
        neighborhoods: NeighborhoodService,
        topics: TopicService,
        assigned: AssignedBillReader,
        sponsors: TopicSponsorReader,
    ) -> None:
        self.neighborhoods = neighborhoods
        self.topics = topics
        self.assigned = assigned
        self.sponsors = sponsors

    def _counts(self, query: TopicNeighborhoodQuery, version: str | None) -> Counter[str]:
        congress = query.neighborhood.congress
        if query.kind is CenterKind.SUBJECT:
            return self.sponsors.by_subject(query.key, congress)
        if version is None or not query.key.lstrip("-").isdigit():
            return Counter()
        field = AssignmentField.TOPIC if query.kind is CenterKind.TOPIC else AssignmentField.METASUBJECT
        bills = self.assigned.read(field, int(query.key), version)
        return self.sponsors.by_bill_ids(bills, congress)

    def _label(self, query: TopicNeighborhoodQuery, version: str | None) -> str:
        if query.kind is CenterKind.SUBJECT or version is None:
            return query.key
        number = int(query.key)
        if query.kind is CenterKind.TOPIC:
            summary = self.topics.topic_summaries(version).get(number)
            return summary.label if summary else f"Topic {number}"
        group = self.topics.metasubject_summaries(version).get(number)
        return group.name if group else f"Group {number}"

    def neighborhood(self, query: TopicNeighborhoodQuery) -> NeighborhoodResponse:
        inner = query.neighborhood
        version, _ = self.topics.latest_model_version()
        counts = self._counts(query, version)
        ranked = [member for member, bills in counts.most_common() if bills >= MIN_BILLS]
        allowed = self.neighborhoods.allowed_members(
            ranked[: inner.limit * CANDIDATE_FACTOR], inner
        )
        kept = [member for member in ranked if member in allowed][: inner.limit]
        if not kept:
            return NeighborhoodResponse(seeds=[], congress=inner.congress)
        versions, links = self.neighborhoods.links_among(kept, inner)
        top = max(counts[member] for member in kept)
        nodes = [
            GraphNode(member=allowed[member], party_group=PartyGroup.of(allowed[member].party))
            for member in kept
        ]
        response = NeighborhoodResponse(
            seeds=[], congress=inner.congress, versions=versions, nodes=nodes, links=links
        )
        label = self._label(query, version)
        match query.kind:
            case CenterKind.TOPIC:
                topic_id = int(query.key)
                response.topic_nodes = [GraphTopicNode(topic_id=topic_id, label=label)]
                response.topic_links = [
                    GraphTopicLink(member=member, topic_id=topic_id, share=counts[member] / top, bills=counts[member])
                    for member in kept
                ]
            case CenterKind.METASUBJECT:
                group_id = int(query.key)
                response.metasubject_nodes = [GraphMetasubjectNode(metasubject_id=group_id, name=label)]
                response.metasubject_links = [
                    GraphMetasubjectLink(member=member, metasubject_id=group_id, share=counts[member] / top, bills=counts[member])
                    for member in kept
                ]
            case CenterKind.SUBJECT:
                response.subject_nodes = [GraphSubjectNode(name=label)]
                response.subject_links = [
                    GraphSubjectLink(member=member, subject=label, bills=counts[member])
                    for member in kept
                ]
        return response

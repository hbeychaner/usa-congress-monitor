"""Serves per-party topic rankings and each topic's party contrast."""

from __future__ import annotations

from cdm.config import PerspectiveConfig
from cdm.contracts.api import (
    BilateralTopicEntry,
    PartiesResponse,
    PartyRanking,
    PartyTopicEntry,
    PartyTopicResponse,
)
from cdm.graph.models import PartyGroup
from cdm.perspectives.models import MAJOR_PARTIES, TopicPerspectives
from cdm.store.perspective_repository import PerspectiveRepository


class PartyService:
    def __init__(
        self, repository: PerspectiveRepository, config: PerspectiveConfig
    ) -> None:
        self.repository = repository
        self.config = config

    def overview(self, congress: int | None) -> PartiesResponse:
        congresses = self.repository.congresses()
        chosen = (
            congress
            if congress is not None
            else (congresses[0] if congresses else None)
        )
        if chosen is None:
            return PartiesResponse(
                congress=None,
                congresses=[],
                model_version=None,
                parties=[],
                bilateral=[],
            )
        topics, version = self.repository.read(chosen)
        return PartiesResponse(
            congress=chosen,
            congresses=congresses,
            model_version=version,
            parties=[self._ranking(party, topics) for party in MAJOR_PARTIES],
            bilateral=self._bilateral(topics),
        )

    def topic(self, congress: int, topic_id: int) -> PartyTopicResponse | None:
        topics, _ = self.repository.read(congress)
        for topic in topics:
            if topic.topic_id == topic_id:
                gated = (
                    topic
                    if topic.passed
                    else topic.model_copy(update={"perspectives": []})
                )
                return PartyTopicResponse(topic=gated)
        return None

    def _ranking(
        self, party: PartyGroup, topics: list[TopicPerspectives]
    ) -> PartyRanking:
        counts = {topic.topic_id: self._party_bills(topic, party) for topic in topics}
        total = sum(counts.values())
        ranked = sorted(
            (topic for topic in topics if counts[topic.topic_id] > 0),
            key=lambda topic: counts[topic.topic_id],
            reverse=True,
        )[: self.config.perspective_ranking_size]
        return PartyRanking(
            party=party,
            total_bills=total,
            topics=[
                PartyTopicEntry(
                    topic_id=topic.topic_id,
                    label=topic.topic_label,
                    bills=counts[topic.topic_id],
                    topic_bills=topic.bills,
                    share_of_party=counts[topic.topic_id] / total,
                    share_of_topic=counts[topic.topic_id] / topic.bills,
                    summary=next(
                        (
                            terms.summary
                            for terms in topic.party_terms
                            if terms.party == party
                        ),
                        "",
                    ),
                )
                for topic in ranked
            ],
        )

    @staticmethod
    def _party_bills(topic: TopicPerspectives, party: PartyGroup) -> int:
        return next(
            (count.bills for count in topic.party_bills if count.party == party), 0
        )

    @staticmethod
    def _bilateral(topics: list[TopicPerspectives]) -> list[BilateralTopicEntry]:
        entries = [
            BilateralTopicEntry(
                topic_id=topic.topic_id,
                label=topic.topic_label,
                bills=topic.bilateral.bills,
                bipartisan_bills=topic.bilateral.bipartisan_bills,
                share=topic.bilateral.share,
                terms=topic.bilateral.terms,
                subjects=topic.bilateral.subjects,
                summary=topic.bilateral.summary,
            )
            for topic in topics
            if topic.bilateral and topic.bilateral.bilateral
        ]
        return sorted(entries, key=lambda entry: entry.share, reverse=True)

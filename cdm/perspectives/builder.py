"""Builds the perspectives of one topic in one Congress from its bills and vectors."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np

from cdm.config import PerspectiveConfig
from cdm.graph.models import PartyGroup
from cdm.perspectives.clustering import ClusterResult, PerspectiveClusterer
from cdm.perspectives.labeler import PerspectiveLabeler
from cdm.perspectives.models import (
    MAJOR_PARTIES,
    BilateralSupport,
    PartyBillCount,
    PartyShare,
    PartyTerms,
    Perspective,
    PerspectiveBill,
    TopicPerspectives,
)
from cdm.perspectives.summarizer import ApproachSummarizer
from cdm.perspectives.terms import DistinctiveTerms

SMOOTHING = 1.0
BIPARTISAN_GROUP = "bipartisan"


@dataclass(frozen=True)
class GroupSummary:
    sample_titles: list[str]
    summary: str


def _log_odds(hits: int, total: int) -> float:
    return float(np.log((hits + SMOOTHING) / (total - hits + SMOOTHING)))


class PerspectiveBuilder:
    """Clusters a topic's bills, then labels each cluster and measures party lean."""

    def __init__(
        self,
        config: PerspectiveConfig,
        clusterer: PerspectiveClusterer,
        terms: DistinctiveTerms,
        labeler: PerspectiveLabeler,
        summarizer: ApproachSummarizer,
    ) -> None:
        self.config = config
        self.clusterer = clusterer
        self.terms = terms
        self.labeler = labeler
        self.summarizer = summarizer

    def build(
        self,
        *,
        congress: int,
        topic_id: int,
        topic_label: str,
        bills: list[PerspectiveBill],
    ) -> TopicPerspectives:
        result = TopicPerspectives(
            congress=congress,
            topic_id=topic_id,
            topic_label=topic_label,
            bills=len(bills),
            party_bills=self._party_bills(bills),
            party_terms=self._party_terms(topic_label, bills),
            bilateral=self._bilateral(topic_label, bills),
        )
        if len(bills) < self.config.perspective_min_bills:
            result.skipped_reason = "too few bills"
            return result
        clusters = self.clusterer.cluster([bill.text for bill in bills])
        if clusters is None:
            result.skipped_reason = "no valid split"
            return result
        result.silhouette = clusters.silhouette
        result.stability = clusters.stability
        result.passed = (
            clusters.silhouette >= self.config.perspective_min_silhouette
            and clusters.stability >= self.config.perspective_min_stability
        )
        terms = self.terms.top([bill.text for bill in bills], clusters.labels)
        result.perspectives = [
            self._perspective(
                congress,
                topic_id,
                topic_label,
                cluster,
                clusters,
                bills,
                terms[cluster],
            )
            for cluster in range(clusters.count)
        ]
        result.perspectives.sort(key=lambda perspective: perspective.size, reverse=True)
        return result

    @staticmethod
    def _party_bills(bills: list[PerspectiveBill]) -> list[PartyBillCount]:
        counts = Counter(bill.sponsor_party for bill in bills if bill.sponsor_party)
        return [
            PartyBillCount(party=party, bills=counts[party]) for party in PartyGroup
        ]

    def _bilateral(
        self, topic_label: str, bills: list[PerspectiveBill]
    ) -> BilateralSupport | None:
        """Share of bills with cosponsors from both parties, and what those bills are about."""
        majors = [bill for bill in bills if bill.sponsor_party in MAJOR_PARTIES]
        if len(majors) < self.config.perspective_party_min_bills:
            return None
        flags = np.array([int(bill.bipartisan) for bill in majors], dtype=np.intp)
        share = float(flags.mean())
        terms = (
            self.terms.top([bill.text for bill in majors], flags).get(1, [])
            if 0 < flags.sum() < len(flags)
            else []
        )
        summary = self._summary(
            topic_label,
            BIPARTISAN_GROUP,
            terms,
            [bill for bill in majors if bill.bipartisan],
        )
        return BilateralSupport(
            bills=len(majors),
            bipartisan_bills=int(flags.sum()),
            share=share,
            bilateral=share >= self.config.perspective_bilateral_min_share,
            terms=terms,
            sample_titles=summary.sample_titles,
            summary=summary.summary,
        )

    def _summary(
        self,
        topic_label: str,
        group: str,
        terms: list[str],
        bills: list[PerspectiveBill],
    ) -> GroupSummary:
        """Sample titles of the bills that best show the terms, and a model summary of them."""
        picks = self.terms.matching(
            [bill.text for bill in bills], terms, self.config.perspective_sample_bills
        )
        titles = [bills[position].title for position in picks]
        return GroupSummary(
            titles, self.summarizer.summarize(topic_label, group, terms, titles)
        )

    def _party_terms(
        self, topic_label: str, bills: list[PerspectiveBill]
    ) -> list[PartyTerms]:
        """Bigrams each major party uses more than the other; empty when a side is too small."""
        sides = list(MAJOR_PARTIES)
        known = [bill for bill in bills if bill.sponsor_party in sides]
        counts = {
            party: sum(bill.sponsor_party == party for bill in known) for party in sides
        }
        if min(counts.values()) < self.config.perspective_party_min_bills:
            return []
        groups = np.array(
            [sides.index(bill.sponsor_party) for bill in known if bill.sponsor_party],
            dtype=np.intp,
        )
        top = self.terms.top([bill.text for bill in known], groups)
        result: list[PartyTerms] = []
        for position, party in enumerate(sides):
            terms = top.get(position, [])
            summary = self._summary(
                topic_label,
                party.value,
                terms,
                [bill for bill in known if bill.sponsor_party == party],
            )
            result.append(
                PartyTerms(
                    party=party,
                    bills=counts[party],
                    terms=terms,
                    sample_titles=summary.sample_titles,
                    summary=summary.summary,
                )
            )
        return result

    def _perspective(
        self,
        congress: int,
        topic_id: int,
        topic_label: str,
        cluster: int,
        clusters: ClusterResult,
        bills: list[PerspectiveBill],
        terms: list[str],
    ) -> Perspective:
        members = [bills[i] for i in np.flatnonzero(clusters.labels == cluster)]
        samples = [
            bills[i].title
            for i in clusters.nearest(cluster, self.config.perspective_sample_bills)
        ]
        return Perspective(
            congress=congress,
            topic_id=topic_id,
            perspective_id=cluster,
            label=self.labeler.label(topic_label, terms, samples),
            size=len(members),
            terms=terms,
            sample_titles=samples,
            parties=self._parties(members, bills),
        )

    @staticmethod
    def _parties(
        members: list[PerspectiveBill], everyone: list[PerspectiveBill]
    ) -> list[PartyShare]:
        known_all = [bill for bill in everyone if bill.sponsor_party]
        known_in = [bill for bill in members if bill.sponsor_party]
        shares: list[PartyShare] = []
        for party in PartyGroup:
            inside = sum(bill.sponsor_party == party for bill in known_in)
            overall = sum(bill.sponsor_party == party for bill in known_all)
            if not overall:
                continue
            shares.append(
                PartyShare(
                    party=party,
                    bills=inside,
                    share=inside / len(known_in) if known_in else 0.0,
                    lean=_log_odds(inside, len(known_in))
                    - _log_odds(overall, len(known_all)),
                )
            )
        return shares

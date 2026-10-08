"""Sponsor and cosponsor collaboration edges between members.

Per-Congress dense matrices are built over one global member index, summed into
an all-time view, and reduced to the top neighbors per member (all-time and per
Congress) so Congress-filtered queries never lose a relevant edge.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict

from cdm.graph.models import BillSignature, CongressEdgeStats, MemberEdge, Signal

Matrix = NDArray[np.float32]


class CollaborationSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    cosign_weight: float = 0.25
    max_cosigners_per_bill: int = 100
    activity_smoothing: float = 3.0
    top_k: int = 50


class CongressMatrices:
    """Collaboration counts for one Congress over the global member index."""

    def __init__(
        self,
        congress: int,
        index: dict[str, int],
        settings: CollaborationSettings,
    ) -> None:
        size = len(index)
        self.congress = congress
        self.index = index
        self.settings = settings
        self.directed: Matrix = np.zeros((size, size), dtype=np.float32)
        self.cosigned: Matrix = np.zeros((size, size), dtype=np.float32)
        self.activity: NDArray[np.float32] = np.zeros(size, dtype=np.float32)

    def add_bill(self, bill: BillSignature) -> None:
        sponsors = [self.index[member] for member in dict.fromkeys(bill.sponsor_ids)]
        sponsor_set = set(sponsors)
        cosponsors = [
            position
            for member in dict.fromkeys(bill.cosponsor_ids)
            if (position := self.index[member]) not in sponsor_set
        ]
        for sponsor in sponsors:
            self.activity[sponsor] += 1
            for cosponsor in cosponsors:
                self.directed[sponsor, cosponsor] += 1
        for cosponsor in cosponsors:
            self.activity[cosponsor] += 1
        if 2 <= len(cosponsors) <= self.settings.max_cosigners_per_bill:
            self.cosigned[np.ix_(cosponsors, cosponsors)] += 1.0 / (len(cosponsors) - 1)

    @property
    def raw(self) -> Matrix:
        raw = self.directed + self.directed.T
        raw += self.settings.cosign_weight * self.cosigned
        np.fill_diagonal(raw, 0.0)
        return raw


class CollaborationGraphBuilder:
    """Turns bill signatures into top-k collaboration edges for every member."""

    def __init__(
        self,
        bills: Sequence[BillSignature],
        graph_version: str,
        settings: CollaborationSettings | None = None,
    ) -> None:
        self.bills = bills
        self.graph_version = graph_version
        self.settings = settings or CollaborationSettings()

    def _score(self, raw: Matrix, activity: NDArray[np.float32]) -> Matrix:
        denominator = np.sqrt(np.outer(activity, activity)) + self.settings.activity_smoothing
        return np.minimum(raw / denominator, 1.0).astype(np.float32)

    def _top_indices(self, row: NDArray[np.float32]) -> NDArray[np.intp]:
        positive = np.flatnonzero(row > 0)
        if len(positive) <= self.settings.top_k:
            return positive
        best = np.argpartition(row[positive], -self.settings.top_k)[-self.settings.top_k :]
        return positive[best]

    def _congress_matrices(self, index: dict[str, int]) -> dict[int, CongressMatrices]:
        grouped: dict[int, CongressMatrices] = {}
        for bill in self.bills:
            if bill.congress not in grouped:
                grouped[bill.congress] = CongressMatrices(
                    bill.congress, index, self.settings
                )
            grouped[bill.congress].add_bill(bill)
        return grouped

    def build(self) -> Iterator[MemberEdge]:
        members = sorted({
            member
            for bill in self.bills
            for member in (*bill.sponsor_ids, *bill.cosponsor_ids)
        })
        index = {member: position for position, member in enumerate(members)}
        by_congress = self._congress_matrices(index)

        size = len(members)
        total_raw: Matrix = np.zeros((size, size), dtype=np.float32)
        total_activity: NDArray[np.float32] = np.zeros(size, dtype=np.float32)
        congress_scores: dict[int, Matrix] = {}
        congress_raw: dict[int, Matrix] = {}
        for congress, matrices in by_congress.items():
            congress_raw[congress] = matrices.raw
            congress_scores[congress] = self._score(
                congress_raw[congress], matrices.activity
            )
            total_raw += congress_raw[congress]
            total_activity += matrices.activity
        total_scores = self._score(total_raw, total_activity)

        for position, member in enumerate(members):
            candidates = set(self._top_indices(total_scores[position]).tolist())
            for scores in congress_scores.values():
                candidates.update(self._top_indices(scores[position]).tolist())
            for neighbor_position in sorted(candidates):
                stats = [
                    CongressEdgeStats(
                        congress=congress,
                        member_sponsored=int(
                            matrices.directed[position, neighbor_position]
                        ),
                        neighbor_sponsored=int(
                            matrices.directed[neighbor_position, position]
                        ),
                        co_signed=float(matrices.cosigned[position, neighbor_position]),
                        score=float(congress_scores[congress][position, neighbor_position]),
                    )
                    for congress, matrices in sorted(by_congress.items())
                    if congress_raw[congress][position, neighbor_position] > 0
                ]
                yield MemberEdge(
                    graph_version=self.graph_version,
                    signal=Signal.COLLABORATION,
                    member=member,
                    neighbor=members[neighbor_position],
                    score=float(total_scores[position, neighbor_position]),
                    by_congress=stats,
                )



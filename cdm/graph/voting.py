"""Roll-call voting edges between members.

Edges score agreement on party-split roll calls, shrunk toward a prior so pairs
with few shared votes are not over-rated. Candidates are the top neighbors per
member, all-time and per Congress.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Self

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict

from cdm.graph.models import CongressEdgeStats, MemberEdge, RollCallVotes, Signal

Matrix = NDArray[np.float32]


class VotingSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    prior_agreement: float = 0.5
    shrinkage_votes: float = 10.0
    top_k: int = 50


class AgreementCounts:
    """Shared and agreed vote counts for every member pair."""

    def __init__(self, size: int) -> None:
        self.shared: Matrix = np.zeros((size, size), dtype=np.float32)
        self.agreed: Matrix = np.zeros((size, size), dtype=np.float32)

    def add_votes(self, votes: Matrix) -> None:
        """Add a members x roll calls matrix of +1 yea, -1 nay, 0 not cast."""
        cast = (votes != 0).astype(np.float32)
        shared = cast @ cast.T
        self.shared += shared
        self.agreed += (votes @ votes.T + shared) / 2

    def __iadd__(self, other: AgreementCounts) -> Self:
        self.shared += other.shared
        self.agreed += other.agreed
        return self


class CongressVotes:
    """All-vote and party-split-vote agreement counts for one Congress."""

    def __init__(self, congress: int, index: dict[str, int]) -> None:
        self.congress = congress
        self.all_votes = AgreementCounts(len(index))
        self.split_votes = AgreementCounts(len(index))

    @classmethod
    def from_rolls(
        cls, congress: int, index: dict[str, int], rolls: Sequence[RollCallVotes]
    ) -> CongressVotes:
        result = cls(congress, index)
        votes = np.zeros((len(index), len(rolls)), dtype=np.float32)
        for column, roll in enumerate(rolls):
            for member in roll.yea_ids:
                votes[index[member], column] = 1.0
            for member in roll.nay_ids:
                votes[index[member], column] = -1.0
        split = np.array([roll.party_split for roll in rolls], dtype=bool)
        result.all_votes.add_votes(votes)
        result.split_votes.add_votes(votes[:, split])
        return result


class VotingGraphBuilder:
    """Turns roll calls into top-k voting edges for every member."""

    def __init__(
        self,
        rolls: Sequence[RollCallVotes],
        graph_version: str,
        settings: VotingSettings | None = None,
    ) -> None:
        self.rolls = rolls
        self.graph_version = graph_version
        self.settings = settings or VotingSettings()

    def _score(self, counts: AgreementCounts) -> Matrix:
        """Shrunk split-vote agreement; zero where the pair never split-voted together."""
        settings = self.settings
        shrunk = (
            counts.agreed + settings.shrinkage_votes * settings.prior_agreement
        ) / (counts.shared + settings.shrinkage_votes)
        shrunk[counts.shared == 0] = 0.0
        np.fill_diagonal(shrunk, 0.0)
        return shrunk.astype(np.float32)

    def _top_indices(self, row: NDArray[np.float32]) -> NDArray[np.intp]:
        positive = np.flatnonzero(row > 0)
        if len(positive) <= self.settings.top_k:
            return positive
        best = np.argpartition(row[positive], -self.settings.top_k)[-self.settings.top_k :]
        return positive[best]

    def build(self) -> Iterator[MemberEdge]:
        members = sorted({
            member
            for roll in self.rolls
            for member in (*roll.yea_ids, *roll.nay_ids)
        })
        index = {member: position for position, member in enumerate(members)}
        rolls_by_congress: dict[int, list[RollCallVotes]] = {}
        for roll in self.rolls:
            rolls_by_congress.setdefault(roll.congress, []).append(roll)

        size = len(members)
        total = CongressVotes(0, index)
        total_all, total_split = AgreementCounts(size), AgreementCounts(size)
        by_congress: dict[int, CongressVotes] = {}
        for congress, rolls in sorted(rolls_by_congress.items()):
            by_congress[congress] = CongressVotes.from_rolls(congress, index, rolls)
            total_all += by_congress[congress].all_votes
            total_split += by_congress[congress].split_votes
        total.all_votes, total.split_votes = total_all, total_split

        congress_scores = {
            congress: self._score(votes.split_votes)
            for congress, votes in by_congress.items()
        }
        total_scores = self._score(total_split)

        for position, member in enumerate(members):
            candidates = set(self._top_indices(total_scores[position]).tolist())
            for scores in congress_scores.values():
                candidates.update(self._top_indices(scores[position]).tolist())
            for neighbor_position in sorted(candidates):
                pair = (position, neighbor_position)
                stats = [
                    CongressEdgeStats(
                        congress=congress,
                        shared_votes=int(votes.all_votes.shared[pair]),
                        agreed_votes=int(votes.all_votes.agreed[pair]),
                        shared_split_votes=int(votes.split_votes.shared[pair]),
                        agreed_split_votes=int(votes.split_votes.agreed[pair]),
                        score=float(congress_scores[congress][pair]),
                    )
                    for congress, votes in by_congress.items()
                    if votes.all_votes.shared[pair] > 0
                ]
                yield MemberEdge(
                    graph_version=self.graph_version,
                    signal=Signal.VOTING,
                    member=member,
                    neighbor=members[neighbor_position],
                    score=float(total_scores[pair]),
                    by_congress=stats,
                )

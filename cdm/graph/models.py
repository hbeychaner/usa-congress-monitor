"""Typed models for the member graph index (edges and version pointers)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
)


class Signal(StrEnum):
    COLLABORATION = "collaboration"
    VOTING = "voting"
    TOPIC = "topic"


class PartyGroup(StrEnum):
    DEMOCRATIC = "democratic"
    REPUBLICAN = "republican"
    OTHER = "other"

    @classmethod
    def of(cls, party_name: str) -> PartyGroup:
        name = party_name.strip().lower()
        if name.startswith("democrat"):
            return cls.DEMOCRATIC
        if name.startswith("republican"):
            return cls.REPUBLICAN
        return cls.OTHER


class DocumentKind(StrEnum):
    EDGE = "edge"
    POINTER = "pointer"


class GraphField(StrEnum):
    """Index field names used when querying the graph index."""

    KIND = "kind"
    SIGNAL = "signal"
    GRAPH_VERSION = "graph_version"
    MEMBER = "member"
    NEIGHBOR = "neighbor"
    SCORE = "score"
    BY_CONGRESS = "by_congress"
    BY_CONGRESS_CONGRESS = "by_congress.congress"
    BY_CONGRESS_SCORE = "by_congress.score"


class BillSignature(BaseModel):
    """The sponsor and cosponsor ids of one bill, read from the legislation index."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str = ""
    congress: int
    sponsor_ids: list[str] = Field(default_factory=list, alias="sponsor_bioguide_ids")
    cosponsor_ids: list[str] = Field(
        default_factory=list, alias="cosponsor_bioguide_ids"
    )

    @field_validator("sponsor_ids", "cosponsor_ids", mode="before")
    @classmethod
    def _none_to_empty(cls, value: object) -> object:
        return [] if value is None else value


class RollCallVotes(BaseModel):
    """The yea and nay voters of one roll call, read from the roll call index."""

    model_config = ConfigDict(extra="ignore")

    congress: int
    party_split: bool = False
    yea_ids: list[str] = Field(default_factory=list)
    nay_ids: list[str] = Field(default_factory=list)


class CongressEdgeStats(BaseModel):
    """Collaboration and voting between two members within one Congress."""

    congress: int
    member_sponsored: int = 0
    neighbor_sponsored: int = 0
    co_signed: float = 0.0
    shared_votes: int = 0
    agreed_votes: int = 0
    shared_split_votes: int = 0
    agreed_split_votes: int = 0
    score: float = 0.0


class MemberEdge(BaseModel):
    """A directed view of one member pair for one signal and graph version."""

    kind: DocumentKind = DocumentKind.EDGE
    graph_version: str
    signal: Signal
    member: str
    neighbor: str
    score: float
    shared_topics: list[str] = Field(default_factory=list)
    by_congress: list[CongressEdgeStats] = Field(default_factory=list)

    @computed_field
    @property
    def id(self) -> str:
        return (
            f"{self.kind}:{self.graph_version}:{self.signal}:"
            f"{self.member}:{self.neighbor}"
        )

    @computed_field
    @property
    def shared_bills(self) -> int:
        return sum(
            stats.member_sponsored + stats.neighbor_sponsored
            for stats in self.by_congress
        )

    @computed_field
    @property
    def shared_votes(self) -> int:
        return sum(stats.shared_votes for stats in self.by_congress)


class GraphVersionPointer(BaseModel):
    """Marks the live graph version for one signal."""

    kind: DocumentKind = DocumentKind.POINTER
    signal: Signal
    graph_version: str
    built_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @computed_field
    @property
    def id(self) -> str:
        return self.pointer_id(self.signal)

    @staticmethod
    def pointer_id(signal: Signal) -> str:
        return f"{DocumentKind.POINTER}:{signal}"

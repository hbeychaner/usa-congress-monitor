"""Typed models for the member graph index (edges and version pointers)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, NewType

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
)

from cdm.contracts.base import ResponseModel

MappingField = NewType("MappingField", str)


class GraphMapping(BaseModel):
    type: str = "object"
    dynamic: bool | Literal["strict"] | None = None
    index: bool = True
    enabled: bool = True
    properties: dict[MappingField, GraphMapping] = Field(default_factory=dict)

    def differences(self, actual: GraphMapping, path: str = "") -> list[str]:
        problems: list[str] = []
        if (
            self.type != actual.type
            or self.index != actual.index
            or self.enabled != actual.enabled
            or self.dynamic is not None
            and self.dynamic != actual.dynamic
        ):
            problems.append(f"{path or '<root>'}: incompatible mapping")
        for name, expected in self.properties.items():
            field_path = f"{path}.{name}" if path else name
            if name not in actual.properties:
                problems.append(f"{field_path}: missing mapping")
            else:
                problems.extend(
                    expected.differences(actual.properties[name], field_path)
                )
        return problems


class GraphIndexDefinition(BaseModel):
    mappings: GraphMapping


class Signal(StrEnum):
    COLLABORATION = "collaboration"
    VOTING = "voting"
    TOPIC = "topic"


class BuildState(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class GraphBuildStatus(ResponseModel):
    state: BuildState = BuildState.IDLE
    job_id: str | None = None
    started: bool | None = None
    pid: int | None = None
    stage: str | None = None
    message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime | None = None
    versions: dict[Signal, str] = Field(default_factory=dict)


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
    present_ids: list[str] = Field(default_factory=list)
    not_voting_ids: list[str] = Field(default_factory=list)


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
    source_model_version: str | None = None
    congresses: list[int] | None = None

    @computed_field
    @property
    def id(self) -> str:
        return self.pointer_id(self.signal)

    @staticmethod
    def pointer_id(signal: Signal) -> str:
        return f"{DocumentKind.POINTER}:{signal}"


class StagedGraph(BaseModel):
    pointer: GraphVersionPointer
    written: int = Field(ge=0)

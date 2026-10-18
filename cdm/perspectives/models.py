"""Typed models for perspective clustering input and output."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from cdm.graph.models import PartyGroup

MAJOR_PARTIES: tuple[PartyGroup, ...] = (PartyGroup.DEMOCRATIC, PartyGroup.REPUBLICAN)


class PerspectiveBill(BaseModel):
    """One bill's text and sponsoring party, ready to cluster."""

    doc_id: str
    title: str
    text: str
    sponsor_party: PartyGroup | None = None
    # True when cosponsors include enough members of the party opposite the sponsor's.
    bipartisan: bool = False


class PartyShare(BaseModel):
    """How many of a perspective's bills one party sponsored."""

    party: PartyGroup
    bills: int
    share: float
    # Smoothed log-odds of this party versus the topic's overall mix; positive leans toward it.
    lean: float


class Perspective(BaseModel):
    """One cluster of a topic's bills within one Congress."""

    model_config = ConfigDict(frozen=True)

    congress: int
    topic_id: int
    perspective_id: int
    label: str
    size: int
    terms: list[str] = Field(default_factory=list)
    sample_titles: list[str] = Field(default_factory=list)
    parties: list[PartyShare] = Field(default_factory=list)


class PartyTerms(BaseModel):
    """Bigrams one party's bills in a topic use more than the other party's."""

    party: PartyGroup
    bills: int
    terms: list[str] = Field(default_factory=list)
    sample_titles: list[str] = Field(default_factory=list)
    summary: str = ""


class BilateralSupport(BaseModel):
    """How much of a topic's legislation draws cosponsors from both parties."""

    bills: int
    bipartisan_bills: int
    share: float
    bilateral: bool
    # Bigrams bipartisan bills use more than the topic's party-line bills.
    terms: list[str] = Field(default_factory=list)
    sample_titles: list[str] = Field(default_factory=list)
    # One-sentence summary of the approach; empty when no language model was available.
    summary: str = ""


class PartyBillCount(BaseModel):
    """Bills in a topic whose primary sponsor belongs to one party."""

    party: PartyGroup
    bills: int


class TopicPerspectives(BaseModel):
    """One topic's party contrast and clusters; clusters count only when ``passed``."""

    congress: int
    topic_id: int
    topic_label: str
    bills: int
    party_bills: list[PartyBillCount] = Field(default_factory=list)
    silhouette: float | None = None
    stability: float | None = None
    passed: bool = False
    party_terms: list[PartyTerms] = Field(default_factory=list)
    bilateral: BilateralSupport | None = None
    perspectives: list[Perspective] = Field(default_factory=list)
    skipped_reason: str = ""

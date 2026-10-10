"""Typed rows produced by topic training and written to the analysis index."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TopicSummaryRow(BaseModel):
    topic_id: int
    name: str
    size: int
    top_words: list[str] = Field(default_factory=list)
    label: str | None = None
    metasubject_id: int | None = None


class TopicTimeBin(BaseModel):
    topic_id: int
    words: str
    frequency: int
    timestamp: str

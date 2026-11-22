"""Taxonomy and record-type base models shared across collections."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RecordTypeBase(BaseModel):
    """Base model that carries the knowledgebase record type."""

    recordType: str = Field(
        default="", description="Which knowledgebase index this record belongs to."
    )


class Subject(BaseModel):
    """Structured subject label with optional update timing."""

    name: str = Field(description="What the subject name is.")
    update_date: datetime | None = Field(
        default=None, description="When the subject was last updated."
    )


class Topic(BaseModel):
    """Structured topic label with optional update timing."""

    topic: str = Field(description="What the topic label is.")
    update_date: datetime | None = Field(
        default=None, description="When the topic was last updated."
    )


__all__ = ["RecordTypeBase", "Subject", "Topic"]

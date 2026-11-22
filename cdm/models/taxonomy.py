"""Taxonomy and record-type base models shared across collections."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class RecordTypeBase(BaseModel):
    """Base model that carries the knowledgebase record type."""

    recordType: str = ""


class Subject(BaseModel):
    """Structured subject label with optional update timing."""

    name: str
    update_date: datetime | None = None


class Topic(BaseModel):
    """Structured topic label with optional update timing."""

    topic: str
    update_date: datetime | None = None


__all__ = ["RecordTypeBase", "Subject", "Topic"]

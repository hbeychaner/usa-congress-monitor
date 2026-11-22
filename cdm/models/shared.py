"""Shared small model fragments used across model modules."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl

from cdm.data_collection.id_utils import UrlIdParser


class Chamber(StrEnum):
    """Enumeration of chambers a member or record can belong to."""

    HOUSE = "House"
    SENATE = "Senate"


class LawType(StrEnum):
    """Enumeration of law types with API slug helpers."""

    PUBLIC = "Public Law"
    PRIVATE = "Private Law"

    def __init__(self, value: str) -> None:
        self._value_ = value
        self.type_url = "pub" if value == "Public Law" else "priv"


class Format(BaseModel):
    """Format metadata for a text version (e.g., PDF, HTML)."""

    type: str
    url: HttpUrl


class Activity(BaseModel):
    """Committee activity entry with an optional source-provided date."""

    date: datetime | None = None
    name: str


class CountUrl(BaseModel):
    """Count and URL pair used by list endpoints."""

    count: int
    url: HttpUrl
    count_including_withdrawn_cosponsors: int | None = Field(
        default=None, alias="countIncludingWithdrawnCosponsors"
    )


class Title(BaseModel):
    """Title entry with type, update date, and text version metadata."""

    title: str
    title_type: str = Field(alias="titleType")
    title_type_code: int = Field(alias="titleTypeCode")
    update_date: datetime = Field(alias="updateDate")
    bill_text_version_code: str = Field(default="", alias="billTextVersionCode")
    bill_text_version_name: str = Field(default="", alias="billTextVersionName")


class SourceSystem(BaseModel):
    """System metadata indicating the source of an action or record."""

    name: str
    code: int = -1


class Note(BaseModel):
    """Notes container for bill metadata entries."""

    text: str


class EntityBase(BaseModel):
    """Base class for item models that provide common identifier fields."""

    id: str | None = None

    def build_id(self) -> str:
        """Return a deterministic identifier for this entity."""
        val = getattr(self, "id", None)
        if val:
            return str(val)

        bioguide = getattr(self, "bioguide_id", None) or getattr(
            self, "bioguideId", None
        )
        if bioguide:
            return f"member:{bioguide}"

        congress = getattr(self, "congress", None)
        number = getattr(self, "number", None)
        typ = getattr(self, "type", None)
        if congress is not None and number is not None and typ is not None:
            return f"bill:{congress}:{str(typ).lower()}:{number}"

        if congress is not None and number is not None:
            chamber = getattr(self, "chamber", None)
            record_type = getattr(self, "recordType", None)
            if isinstance(record_type, str) and record_type:
                resource = record_type.replace("congress-", "").replace("-", "_")
            else:
                resource = self.__class__.__name__.lower()
            return (
                f"{resource}:{congress}:{chamber}:{number}"
                if chamber
                else f"{resource}:{congress}:{number}"
            )

        url = getattr(self, "url", None)
        if url:
            return UrlIdParser.parse(str(url))

        raise ValueError(
            f"Could not build canonical id for {self.__class__.__name__}: no id-bioguide-congress/number-or-url present"
        )

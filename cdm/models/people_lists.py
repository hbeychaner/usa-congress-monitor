"""List-level member models and related depictions."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, Field, HttpUrl, model_validator

from cdm.models.shared import EntityBase
from cdm.models.taxonomy import RecordTypeBase


class MemberDepiction(BaseModel):
    """Member image metadata used in list responses."""

    attribution: str | None = None
    image_url: HttpUrl | None = Field(default=None, alias="imageUrl")


class MemberTermItem(BaseModel):
    """Single term entry used in member list responses."""

    chamber: str | None = None
    start_year: int | None = Field(default=None, alias="startYear")
    end_year: int | None = Field(default=None, alias="endYear")


class MemberTerms(BaseModel):
    """Container for member term entries in list responses."""

    item: list[MemberTermItem] | None = None


class MemberListItem(EntityBase, RecordTypeBase):
    """List-level member entry with name, party, and term data."""

    @model_validator(mode="before")
    @classmethod
    def _populate_bioguide_id_from_url(cls, values):
        if isinstance(values, dict) and not (
            values.get("bioguideId") or values.get("bioguide_id")
        ):
            url = values.get("url")
            if url:
                parts = [p for p in urlparse(str(url)).path.split("/") if p]
                if len(parts) >= 2 and parts[-2].lower() == "member":
                    values["bioguideId"] = parts[-1]
        return values

    recordType: str = "congress-members"
    bioguide_id: str = Field(alias="bioguideId")
    state: str | None = None
    party_name: str | None = Field(default=None, alias="partyName")
    district: int | None = None
    name: str | None = None
    depiction: MemberDepiction | None = None
    terms: MemberTerms | None = None
    update_date: datetime | None = Field(default=None, alias="updateDate")
    url: HttpUrl | None = None


__all__ = [
    "MemberDepiction",
    "MemberListItem",
    "MemberTermItem",
    "MemberTerms",
]

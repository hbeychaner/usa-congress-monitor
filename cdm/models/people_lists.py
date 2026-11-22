"""List-level member models and related depictions."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, Field, HttpUrl, model_validator

from cdm.models.shared import EntityBase
from cdm.models.taxonomy import RecordTypeBase


class MemberDepiction(BaseModel):
    """Member image metadata used in list responses."""

    attribution: str | None = Field(
        default=None, description="Who to credit for the member image."
    )
    image_url: HttpUrl | None = Field(
        default=None,
        alias="imageUrl",
        description="Where to fetch the member image.",
    )


class MemberTermItem(BaseModel):
    """Single term entry used in member list responses."""

    chamber: str | None = Field(
        default=None, description="Which chamber the term was served in."
    )
    start_year: int | None = Field(
        default=None, alias="startYear", description="What year the term started."
    )
    end_year: int | None = Field(
        default=None, alias="endYear", description="What year the term ended."
    )


class MemberTerms(BaseModel):
    """Container for member term entries in list responses."""

    item: list[MemberTermItem] | None = Field(
        default=None, description="Which terms are listed for the member."
    )


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
                path_parts = [
                    part for part in urlparse(str(url)).path.split("/") if part
                ]
                if len(path_parts) >= 2 and path_parts[-2].lower() == "member":
                    values["bioguideId"] = path_parts[-1]
        return values

    recordType: str = Field(
        default="congress-members",
        description="Which knowledgebase index this record belongs to.",
    )
    bioguide_id: str = Field(
        alias="bioguideId", description="What the member's Bioguide identifier is."
    )
    state: str | None = Field(
        default=None,
        description="Which state or territory the member represents.",
    )
    party_name: str | None = Field(
        default=None,
        alias="partyName",
        description="What the member's party name is.",
    )
    district: int | None = Field(
        default=None,
        description="Which congressional district the member represents.",
    )
    name: str | None = Field(
        default=None, description="What the member's display name is."
    )
    depiction: MemberDepiction | None = Field(
        default=None,
        description="What image information is available for the member.",
    )
    terms: MemberTerms | None = Field(
        default=None, description="Which terms are listed for the member."
    )
    update_date: datetime | None = Field(
        default=None,
        alias="updateDate",
        description="When the member record was last updated.",
    )
    url: HttpUrl | None = Field(
        default=None, description="Where to retrieve the member record in the API."
    )


__all__ = [
    "MemberDepiction",
    "MemberListItem",
    "MemberTermItem",
    "MemberTerms",
]

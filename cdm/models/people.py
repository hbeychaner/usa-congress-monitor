"""Pydantic models for people, Congress metadata, and membership terms."""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import (
    AliasChoices,
    BaseModel,
    Field,
    HttpUrl,
    ValidationError,
    model_validator,
)

from cdm.data_collection.id_utils import UrlIdParser
from cdm.models.shared import Chamber, CountUrl, EntityBase

logger = logging.getLogger(__name__)


class Session(BaseModel):
    """Single congressional session metadata with start/end dates and type."""

    chamber: str
    end_date: datetime | None = Field(default=None, alias="endDate")
    number: int | None = Field(default=0, alias="number")
    start_date: datetime = Field(alias="startDate")
    type: str


class Congress(BaseModel):
    """Congress metadata including sessions and coverage years."""

    number: int
    url: HttpUrl
    update_date: datetime = Field(alias="updateDate")
    start_year: int = Field(alias="startYear")
    end_year: int = Field(alias="endYear")
    name: str
    sessions: list[Session]


class CongressMetadata(BaseModel):
    """Minimal Congress metadata used in nested API responses."""

    number: int | None = None
    url: HttpUrl | None = None
    name: str | None = None
    update_date: datetime | None = Field(default=None, alias="updateDate")
    sessions: list[Session] = []
    start_year: int | None = Field(default=None, alias="startYear")
    end_year: int | None = Field(default=None, alias="endYear")


class Depiction(BaseModel):
    """Member image metadata including attribution and image URL."""

    attribution: str = ""
    image_url: HttpUrl | None = Field(default=None, alias="imageUrl")

    @staticmethod
    def empty() -> Depiction:
        """Return an empty depiction placeholder with no image URL."""
        return Depiction(attribution="", image_url=None)


class MemberAddress(BaseModel):
    """Member office/address contact details."""

    city: str | None = None
    district: str | None = None
    office_address: str | None = Field(default=None, alias="officeAddress")
    phone_number: str | None = Field(default=None, alias="phoneNumber")
    zip_code: int | None = Field(default=None, alias="zipCode")

    model_config = {"populate_by_name": True}


class Member(EntityBase):
    """Congressional member record with identity, affiliation, and depiction."""

    bioguide_id: str = Field(alias="bioguideId")
    first_name: str = Field(alias="firstName")
    full_name: str = Field(
        serialization_alias="fullName",
        validation_alias=AliasChoices(
            "fullName", "name", "directOrderName", "invertedOrderName"
        ),
    )
    last_name: str = Field(alias="lastName")
    party: str | None = Field(
        default=None, validation_alias=AliasChoices("party", "partyName")
    )
    state: str
    url: HttpUrl | None = None
    middle_name: str = Field(default="", alias="middleName")
    district: int | None = None
    is_original_cosponsor: bool = Field(default=False, alias="isOriginalCosponsor")
    is_by_request: str = Field(default="", alias="isByRequest")
    depiction: Depiction = Field(default_factory=Depiction.empty, alias="depiction")
    address_information: MemberAddress | None = Field(
        default=None, alias="addressInformation"
    )
    official_website_url: HttpUrl | None = Field(
        default=None, alias="officialWebsiteUrl"
    )
    leadership: list[dict] | None = Field(default=None, alias="leadership")
    birth_year: str | None = Field(default=None, alias="birthYear")
    death_year: str | None = Field(default=None, alias="deathYear")
    current_member: bool | None = Field(default=None, alias="currentMember")
    honorific_name: str | None = Field(default=None, alias="honorificName")
    direct_order_name: str | None = Field(default=None, alias="directOrderName")
    inverted_order_name: str | None = Field(default=None, alias="invertedOrderName")
    update_date: datetime | None = Field(default=None, alias="updateDate")
    member_type: str | None = Field(default=None, alias="memberType")
    state_code: str | None = Field(default=None, alias="stateCode")
    cosponsored_legislation: CountUrl | None = Field(
        default=None, alias="cosponsoredLegislation"
    )
    sponsored_legislation: CountUrl | None = Field(
        default=None, alias="sponsoredLegislation"
    )

    class PartyHistoryItem(BaseModel):
        party_abbreviation: str | None = Field(default=None, alias="partyAbbreviation")
        party_name: str | None = Field(default=None, alias="partyName")
        start_year: int | None = Field(default=None, alias="startYear")

    party_history: list[PartyHistoryItem] | None = Field(
        default=None, alias="partyHistory"
    )

    class PreviousName(BaseModel):
        direct_order_name: str | None = Field(default=None, alias="directOrderName")
        end_date: datetime | None = Field(default=None, alias="endDate")
        first_name: str | None = Field(default=None, alias="firstName")
        honorific_name: str | None = Field(default=None, alias="honorificName")
        inverted_order_name: str | None = Field(default=None, alias="invertedOrderName")
        last_name: str | None = Field(default=None, alias="lastName")
        middle_name: str | None = Field(default=None, alias="middleName")
        start_date: datetime | None = Field(default=None, alias="startDate")

    previous_names: list[PreviousName] | None = Field(
        default=None, alias="previousNames"
    )

    class MemberTermFull(BaseModel):
        chamber: str | None = None
        congress: int | None = None
        district: int | None = None
        end_year: int | None = Field(default=None, alias="endYear")
        member_type: str | None = Field(default=None, alias="memberType")
        start_year: int | None = Field(default=None, alias="startYear")
        state_code: str | None = Field(default=None, alias="stateCode")
        state_name: str | None = Field(default=None, alias="stateName")

    terms: list[MemberTermFull] | None = Field(default=None, alias="terms")

    def build_id(self) -> str:
        """Return a canonical id for this member instance."""
        bid = getattr(self, "bioguide_id", None)
        if bid:
            return f"person:{bid}"
        url = getattr(self, "url", None)
        if url:
            try:
                return UrlIdParser.parse(str(url))
            except (TypeError, ValueError):
                logger.exception("Failed to parse URL to id in Member.build_id")
        try:
            return f"record:{abs(hash(str(self.model_dump()))) % (10**12)}"
        except (AttributeError, TypeError, ValueError):
            return f"record:{abs(hash(str(getattr(self, 'full_name', 'member')))) % (10**12)}"

    @model_validator(mode="after")
    def _populate_common_fields(self):
        if not getattr(self, "id", None):
            try:
                self.id = self.build_id()
            except (AttributeError, TypeError, ValueError):
                logger.debug("Could not build an id for Member")

        if not getattr(self, "url", None):
            bid = getattr(self, "bioguide_id", None)
            if bid:
                try:
                    self.url = HttpUrl(
                        f"https://api.congress.gov/v3/member/{bid}?format=json"
                    )
                except (TypeError, ValueError, ValidationError):
                    logger.debug("Could not build a URL for Member %s", bid)

        terms = getattr(self, "terms", None)
        if isinstance(terms, list) and terms:
            first = terms[0]
            if not getattr(self, "member_type", None):
                mt = (
                    first.get("memberType")
                    if isinstance(first, dict)
                    else getattr(first, "member_type", None)
                )
                if mt:
                    self.member_type = mt
            if not getattr(self, "state_code", None):
                sc = (
                    first.get("stateCode")
                    if isinstance(first, dict)
                    else getattr(first, "state_code", None)
                )
                if sc:
                    self.state_code = sc

        return self

    @model_validator(mode="before")
    def _populate_from_alternate_fields(cls, values: dict):
        if "fullName" not in values:
            if values.get("directOrderName"):
                values["fullName"] = values["directOrderName"]
            elif values.get("invertedOrderName"):
                values["fullName"] = values["invertedOrderName"]

        if not values.get("party"):
            ph = values.get("partyHistory")
            if isinstance(ph, list) and ph and isinstance(ph[0], dict):
                values["party"] = ph[0].get("partyName") or ph[0].get(
                    "partyAbbreviation"
                )

        return values


class Sponsor(Member):
    """A member acting as sponsor, with sponsorship timing metadata."""

    @model_validator(mode="before")
    @classmethod
    def _tolerate_sparse_sponsor(cls, values: object) -> object:
        if not isinstance(values, dict):
            return values
        cleaned = dict(values)
        for key in ("sponsorshipDate", "sponsorshipWithdrawnDate"):
            if cleaned.get(key) == "":
                cleaned[key] = None
        if cleaned.get("state") is None:
            cleaned["state"] = ""
        return cleaned

    sponsorship_date: datetime | None = Field(default=None, alias="sponsorshipDate")
    is_original_cosponsor: bool = Field(default=False, alias="isOriginalCosponsor")
    sponsorship_withrawn_date: datetime | None = Field(
        default=None, alias="sponsorshipWithdrawnDate"
    )


class SponsorRef(BaseModel):
    """Permissive sponsor reference for non-person sponsors (committees, orgs)."""

    bioguide_id: str | None = Field(default=None, alias="bioguideId")
    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    full_name: str | None = Field(default=None, alias="fullName")
    state: str | None = None
    url: HttpUrl | None = None


__all__ = [
    "Chamber",
    "Congress",
    "CongressMetadata",
    "Depiction",
    "Member",
    "MemberAddress",
    "Session",
    "Sponsor",
    "SponsorRef",
]

"""Pydantic models for people, Congress metadata, and membership terms.

Each model includes per-field descriptions that explain what each attribute answers.
"""

import logging
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import (
    AliasChoices,
    BaseModel,
    Field,
    HttpUrl,
    ValidationError,
    model_validator,
)

from cdm.data_collection.id_utils import parse_url_to_id
from cdm.models.shared import CountUrl, EntityBase

logger = logging.getLogger(__name__)


class Chamber(StrEnum):
    """Enumeration of chambers a member or record can belong to."""

    HOUSE = "House"
    SENATE = "Senate"


class Session(BaseModel):
    """Single congressional session metadata with start/end dates and type."""

    chamber: Annotated[str, Field(description="Which chamber the session belongs to.")]
    end_date: Annotated[
        datetime,
        Field(alias="endDate", default=None, description="When the session ended."),
    ]
    number: Annotated[
        int | None,
        Field(alias="number", default=0, description="What the session number is."),
    ]
    start_date: Annotated[
        datetime, Field(alias="startDate", description="When the session started.")
    ]
    type: Annotated[str, Field(description="What type of session this is.")]


class Congress(BaseModel):
    """Congress metadata including sessions and coverage years."""

    number: Annotated[
        int, Field(description="Which Congress number this record is for.")
    ]
    url: Annotated[
        HttpUrl, Field(description="Where to retrieve the Congress record in the API.")
    ]
    update_date: Annotated[
        datetime,
        Field(
            alias="updateDate", description="When the Congress record was last updated."
        ),
    ]
    start_year: Annotated[
        int, Field(alias="startYear", description="What year this Congress started.")
    ]
    end_year: Annotated[
        int, Field(alias="endYear", description="What year this Congress ended.")
    ]
    name: Annotated[str, Field(description="What the display name of the Congress is.")]
    sessions: Annotated[
        list[Session],
        Field(description="Which sessions are included in this Congress."),
    ]


class CongressMetadata(BaseModel):
    """Minimal Congress metadata used in nested API responses."""

    number: Annotated[
        int | None,
        Field(
            default=None, description="Which Congress number this metadata refers to."
        ),
    ]
    url: Annotated[
        HttpUrl | None, Field(default=None, description="Link to the congress item")
    ]
    name: Annotated[
        str | None, Field(default=None, description="Display name of the congress")
    ] = None
    update_date: Annotated[
        datetime | None,
        Field(
            alias="updateDate",
            default=None,
            description="When the Congress record was last updated.",
        ),
    ] = None
    sessions: list[Session] = []
    start_year: Annotated[
        int | None, Field(alias="startYear", default=None, description="Start year")
    ] = None
    end_year: Annotated[
        int | None, Field(alias="endYear", default=None, description="End year")
    ] = None


class Depiction(BaseModel):
    """Member image metadata including attribution and image URL."""

    attribution: Annotated[
        str, Field(default="", description="Who to credit for the member image.")
    ] = ""
    image_url: Annotated[
        HttpUrl | None,
        Field(
            alias="imageUrl",
            default=None,
            description="Where to fetch the member image.",
        ),
    ]

    @staticmethod
    def empty() -> "Depiction":
        """Return an empty depiction placeholder with no image URL."""
        return Depiction(attribution="", image_url=None)


class MemberAddress(BaseModel):
    """Member office/address contact details."""

    city: Annotated[str | None, Field(default=None)] = None
    district: Annotated[str | None, Field(default=None)] = None
    office_address: Annotated[
        str | None, Field(default=None, alias="officeAddress")
    ] = None
    phone_number: Annotated[str | None, Field(default=None, alias="phoneNumber")] = None
    zip_code: Annotated[int | None, Field(default=None, alias="zipCode")] = None

    model_config = {"populate_by_name": True}


class Term(BaseModel):
    """Service term for a member, including chamber and year range."""

    chamber: Annotated[
        Chamber, Field(description="Which chamber the term was served in.")
    ]
    end_year: Annotated[
        int,
        Field(alias="endYear", default=None, description="What year the term ended."),
    ]
    start_year: Annotated[
        int,
        Field(
            alias="startYear", default=None, description="What year the term started."
        ),
    ]


class Member(EntityBase):
    """Congressional member record with identity, affiliation, and depiction."""

    bioguide_id: Annotated[
        str, Field(alias="bioguideId", description="What the Bioguide identifier is.")
    ]
    first_name: Annotated[
        str, Field(alias="firstName", description="What the member's first name is.")
    ]
    full_name: Annotated[
        str,
        Field(
            validation_alias=AliasChoices(
                "fullName", "name", "directOrderName", "invertedOrderName"
            ),
            description="What the member's full display name is.",
        ),
    ]
    last_name: Annotated[
        str, Field(alias="lastName", description="What the member's last name is.")
    ]
    party: Annotated[
        str | None,
        Field(
            default=None,
            validation_alias=AliasChoices("party", "partyName"),
            description="Which party the member belongs to.",
        ),
    ]
    state: Annotated[
        str, Field(description="Which state or territory the member represents.")
    ]
    url: Annotated[
        HttpUrl | None,
        Field(
            default=None, description="Where to retrieve the member record in the API."
        ),
    ]
    middle_name: Annotated[
        str,
        Field(
            alias="middleName",
            description="What the member's middle name or initial is.",
        ),
    ] = ""
    district: Annotated[
        int | None,
        Field(description="Which congressional district the member represents."),
    ] = None
    is_original_cosponsor: Annotated[
        bool,
        Field(
            alias="isOriginalCosponsor",
            description="Whether the member was an original cosponsor.",
        ),
    ] = False
    is_by_request: Annotated[
        str,
        Field(
            alias="isByRequest",
            description="Whether the measure was introduced by request.",
        ),
    ] = ""
    depiction: Annotated[
        Depiction,
        Field(
            alias="depiction",
            description="What image information is available for the member.",
        ),
    ] = Depiction.empty()
    address_information: Annotated[
        MemberAddress | None,
        Field(
            default=None,
            alias="addressInformation",
            description="Member address/contact info.",
        ),
    ] = None
    official_website_url: Annotated[
        HttpUrl | None,
        Field(
            default=None,
            alias="officialWebsiteUrl",
            description="Member's official/personal website.",
        ),
    ] = None
    leadership: Annotated[
        list[dict] | None,
        Field(
            default=None,
            alias="leadership",
            description="Leadership role info when present.",
        ),
    ] = None

    # Additional item-level fields returned by the API
    birth_year: Annotated[
        str | None, Field(default=None, alias="birthYear", description="Birth year")
    ] = None
    death_year: Annotated[
        str | None, Field(default=None, alias="deathYear", description="Death year")
    ] = None
    current_member: Annotated[
        bool | None,
        Field(default=None, alias="currentMember", description="Is current member"),
    ] = None
    honorific_name: Annotated[
        str | None,
        Field(default=None, alias="honorificName", description="Honorific"),
    ] = None
    direct_order_name: Annotated[
        str | None,
        Field(
            default=None,
            alias="directOrderName",
            description="Direct-order display name",
        ),
    ] = None
    inverted_order_name: Annotated[
        str | None,
        Field(
            default=None,
            alias="invertedOrderName",
            description="Inverted-order display name",
        ),
    ] = None

    update_date: Annotated[
        datetime | None,
        Field(
            default=None,
            alias="updateDate",
            description="When the member record was last updated",
        ),
    ] = None

    member_type: Annotated[
        str | None,
        Field(
            default=None,
            alias="memberType",
            description="Member type (e.g., Representative, Senator)",
        ),
    ] = None

    state_code: Annotated[
        str | None,
        Field(default=None, alias="stateCode", description="State code for the member"),
    ] = None

    cosponsored_legislation: Annotated[
        CountUrl | None,
        Field(
            default=None,
            alias="cosponsoredLegislation",
            description="Cosponsored legislation count/url",
        ),
    ] = None
    sponsored_legislation: Annotated[
        CountUrl | None,
        Field(
            default=None,
            alias="sponsoredLegislation",
            description="Sponsored legislation count/url",
        ),
    ] = None

    class PartyHistoryItem(BaseModel):
        party_abbreviation: Annotated[
            str | None, Field(default=None, alias="partyAbbreviation")
        ]
        party_name: Annotated[str | None, Field(default=None, alias="partyName")]
        start_year: Annotated[int | None, Field(default=None, alias="startYear")]

    party_history: Annotated[
        list[PartyHistoryItem] | None,
        Field(
            default=None,
            alias="partyHistory",
            description="Historic party affiliations",
        ),
    ] = None

    class PreviousName(BaseModel):
        direct_order_name: Annotated[
            str | None, Field(default=None, alias="directOrderName")
        ]
        end_date: Annotated[datetime | None, Field(default=None, alias="endDate")]
        first_name: Annotated[str | None, Field(default=None, alias="firstName")]
        honorific_name: Annotated[
            str | None, Field(default=None, alias="honorificName")
        ]
        inverted_order_name: Annotated[
            str | None, Field(default=None, alias="invertedOrderName")
        ]
        last_name: Annotated[str | None, Field(default=None, alias="lastName")]
        middle_name: Annotated[str | None, Field(default=None, alias="middleName")]
        start_date: Annotated[datetime | None, Field(default=None, alias="startDate")]

    previous_names: Annotated[
        list[PreviousName] | None,
        Field(
            default=None, alias="previousNames", description="Previous name variants"
        ),
    ] = None

    class MemberTermFull(BaseModel):
        chamber: Annotated[str | None, Field(default=None)] = None
        congress: Annotated[int | None, Field(default=None)] = None
        district: Annotated[int | None, Field(default=None)] = None
        end_year: Annotated[int | None, Field(default=None, alias="endYear")] = None
        member_type: Annotated[str | None, Field(default=None, alias="memberType")] = (
            None
        )
        start_year: Annotated[int | None, Field(default=None, alias="startYear")] = None
        state_code: Annotated[str | None, Field(default=None, alias="stateCode")] = None
        state_name: Annotated[str | None, Field(default=None, alias="stateName")] = None

    terms: Annotated[
        list[MemberTermFull] | None,
        Field(
            default=None, alias="terms", description="Full term entries for the member"
        ),
    ] = None

    def build_id(self) -> str:
        """Return a canonical id for this member instance.

        Always returns a string. Falls back to a hashed record id when no
        explicit identifier is present.
        """
        bid = getattr(self, "bioguide_id", None)
        if bid:
            return f"person:{bid}"
        # fallback: stable hashed id from model dump
        url = getattr(self, "url", None)
        if url:
            try:
                return parse_url_to_id(str(url))
            except (TypeError, ValueError):
                logger.exception("Failed to parse URL to id in Member.build_id")
        try:
            mapping = self.model_dump()
            return f"record:{abs(hash(str(mapping))) % (10**12)}"
        except (AttributeError, TypeError, ValueError):
            return f"record:{abs(hash(str(getattr(self, 'full_name', 'member')))) % (10**12)}"

    @model_validator(mode="after")
    def _populate_common_fields(self):
        """Ensure `id`, `url`, `member_type`, and `state_code` are populated when possible.

        - Sets `id` using `build_id()` when missing.
        - Synthesizes an API `url` from `bioguide_id` when missing.
        - Copies `member_type` and `state_code` from the first `terms` entry when absent.
        """
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

        if not getattr(self, "member_type", None):
            terms = getattr(self, "terms", None)
            if isinstance(terms, list) and terms:
                first = terms[0]
                mt = first.get("memberType") if isinstance(first, dict) else None
                if not mt:
                    mt = getattr(first, "member_type", None)
                if mt:
                    self.member_type = mt

        if not getattr(self, "state_code", None):
            terms = getattr(self, "terms", None)
            if isinstance(terms, list) and terms:
                first = terms[0]
                sc = first.get("stateCode") if isinstance(first, dict) else None
                if not sc:
                    sc = getattr(first, "state_code", None)
                if sc:
                    self.state_code = sc

        return self

    @model_validator(mode="before")
    def _populate_from_alternate_fields(cls, values: dict):
        # Populate `fullName` from `directOrderName` or `invertedOrderName` when present
        if "fullName" not in values:
            if "directOrderName" in values and values.get("directOrderName"):
                values["fullName"] = values.get("directOrderName")
            elif "invertedOrderName" in values and values.get("invertedOrderName"):
                values["fullName"] = values.get("invertedOrderName")

        # Populate `party` from `partyHistory` if available
        if "party" not in values or not values.get("party"):
            ph = values.get("partyHistory")
            if isinstance(ph, list) and ph:
                first = ph[0]
                if isinstance(first, dict):
                    values["party"] = first.get("partyName") or first.get(
                        "partyAbbreviation"
                    )

        return values


class Sponsor(Member):
    """A member acting as sponsor, with sponsorship timing metadata."""

    sponsorship_date: Annotated[
        datetime | None,
        Field(
            alias="sponsorshipDate", default=None, description="When sponsorship began."
        ),
    ]
    is_original_cosponsor: Annotated[
        bool,
        Field(
            alias="isOriginalCosponsor",
            description="Whether the sponsor was an original cosponsor.",
        ),
    ] = False
    sponsorship_withrawn_date: Annotated[
        datetime | None,
        Field(
            alias="sponsorshipWithdrawnDate",
            description="When sponsorship was withdrawn, if applicable.",
        ),
    ] = None


class SponsorRef(BaseModel):
    """Permissive sponsor reference for non-person sponsors (committees, orgs).

    Some API endpoints return sponsor entries that are committees or simple
    references containing only a `name` or `url`. This lightweight model
    accepts partial sponsor data so parent models can validate without
    failing when a full `Member` object isn't available.
    """

    bioguide_id: Annotated[str | None, Field(default=None, alias="bioguideId")] = None
    first_name: Annotated[str | None, Field(default=None, alias="firstName")] = None
    last_name: Annotated[str | None, Field(default=None, alias="lastName")] = None
    full_name: Annotated[str | None, Field(default=None, alias="fullName")] = None
    state: Annotated[str | None, Field(default=None)] = None
    url: Annotated[HttpUrl | None, Field(default=None)] = None

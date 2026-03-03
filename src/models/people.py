"""Pydantic models for people, Congress metadata, and membership terms.

Each model includes per-field descriptions that explain what each attribute answers.
"""

from datetime import datetime
from enum import StrEnum
from pydantic import AliasChoices, BaseModel, HttpUrl, Field
from typing import List, Annotated, Optional


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
        List[Session],
        Field(description="Which sessions are included in this Congress."),
    ]


class CongressMetadata(BaseModel):
    """Minimal Congress metadata used in nested API responses."""

    number: Annotated[
        int, Field(description="Which Congress number this metadata refers to.")
    ]


class Depiction(BaseModel):
    """Member image metadata including attribution and image URL."""

    attribution: Annotated[
        str, Field(description="Who to credit for the member image.")
    ]
    image_url: Annotated[
        Optional[HttpUrl],
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


class Member(BaseModel):
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
            validation_alias=AliasChoices("fullName", "name"),
            description="What the member's full display name is.",
        ),
    ]
    last_name: Annotated[
        str, Field(alias="lastName", description="What the member's last name is.")
    ]
    party: Annotated[
        str,
        Field(
            validation_alias=AliasChoices("party", "partyName"),
            description="Which party the member belongs to.",
        ),
    ]
    state: Annotated[
        str, Field(description="Which state or territory the member represents.")
    ]
    url: Annotated[
        HttpUrl, Field(description="Where to retrieve the member record in the API.")
    ]
    middle_name: Annotated[
        str,
        Field(
            alias="middleName",
            description="What the member's middle name or initial is.",
        ),
    ] = ""
    district: Annotated[
        Optional[int],
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


class Sponsor(Member):
    """A member acting as sponsor, with sponsorship timing metadata."""

    sponsorship_date: Annotated[
        datetime, Field(alias="sponsorshipDate", description="When sponsorship began.")
    ]
    is_original_cosponsor: Annotated[
        bool,
        Field(
            alias="isOriginalCosponsor",
            description="Whether the sponsor was an original cosponsor.",
        ),
    ] = False
    sponsorship_withrawn_date: Annotated[
        Optional[datetime],
        Field(
            alias="sponsorshipWithdrawnDate",
            description="When sponsorship was withdrawn, if applicable.",
        ),
    ] = None

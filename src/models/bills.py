"""Pydantic models for bills, amendments, laws, committees, and related metadata.

Each model includes per-field descriptions that explain what each attribute answers.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, List, Optional, Union

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator
import logging

from src.data_collection.client import CDGClient
from src.data_collection.id_utils import parse_url_to_id
from src.models.people import Chamber, Member, Sponsor, SponsorRef
from src.models.shared import (
    Activity,
    CountUrl,
    EntityBase,
    Format,
    Note,
    SourceSystem,
    Title,
)
from src.models.validators import convert_law_type, normalize_chamber

logger = logging.getLogger(__name__)

# The API returns CountUrl envelopes for these fields (never expanded lists).
# Keep the typing succinct: these fields are `CountUrl` when present.


class Hearing(BaseModel):
    """Hearing metadata with title, chamber, committee, and timing details."""

    title: Annotated[str, Field(description="What the hearing title is.")]
    url: Annotated[
        Optional[HttpUrl],
        Field(default=None, description="Where to retrieve the hearing in the API."),
    ] = None
    chamber: Annotated[
        Optional[Chamber], Field(description="Which chamber held the hearing.")
    ] = None
    committee_name: Annotated[
        Optional[str], Field(description="Which committee held the hearing.")
    ] = None
    hearing_date: Annotated[
        Optional[datetime], Field(description="When the hearing took place.")
    ] = None
    type: Annotated[
        Optional[str], Field(description="What type of hearing this is.")
    ] = None
    # Additional API-provided fields preserved from the hearing envelope
    citation: Annotated[
        Optional[str], Field(default=None, description="Official hearing citation.")
    ] = None
    jacket_number: Annotated[
        Optional[int],
        Field(
            default=None,
            alias="jacketNumber",
            description="Jacket number assigned by the source.",
        ),
    ] = None
    library_of_congress_identifier: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="libraryOfCongressIdentifier",
            description="Library of Congress identifier.",
        ),
    ] = None
    congress: Annotated[
        Optional[int],
        Field(default=None, description="Which Congress the hearing belongs to."),
    ] = None
    dates: Annotated[
        Optional[list[dict]],
        Field(default=None, description="Raw dates array from the API."),
    ] = None
    formats: Annotated[
        Optional[list[dict]],
        Field(
            default=None,
            description="Raw formats array (may include formatted text/PDF entries).",
        ),
    ] = None
    associated_meeting: Annotated[
        Optional[dict],
        Field(
            default=None,
            alias="associatedMeeting",
            description="Associated committee meeting object when present.",
        ),
    ] = None
    part: Annotated[
        Optional[int],
        Field(
            default=None, description="Part number when a hearing spans multiple parts."
        ),
    ] = None
    number: Annotated[
        Optional[int],
        Field(default=None, description="Hearing number when provided."),
    ] = None
    update_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="updateDate",
            description="When the hearing record was last updated.",
        ),
    ] = None
    committees: Annotated[
        Optional[list[dict]],
        Field(
            default=None,
            description="Raw committee objects included in the hearing envelope.",
        ),
    ] = None
    # Preserve the original API envelope when available (kept for forensics)
    hearing: Annotated[
        Optional[dict],
        Field(
            default=None,
            alias="hearing",
            description="Original API hearing envelope (preserved for forensics).",
        ),
    ] = None

    @model_validator(mode="before")
    def _populate_url_from_formats(cls, values: dict):
        # If the API returns a `formats` list with URLs, use the first URL
        if not values.get("url"):
            fmts = values.get("formats")
            if isinstance(fmts, list) and fmts:
                first = fmts[0]
                if isinstance(first, dict) and first.get("url"):
                    values["url"] = first.get("url")
        return values

    @model_validator(mode="before")
    def _extract_from_envelope(cls, values: dict):
        # If the API response included a `hearing` envelope, preserve it
        # and populate a few convenient flattened fields when absent.
        env = values.get("hearing")
        # Some callers pass the envelope directly (candidate = r.get('hearing')),
        # so treat the incoming dict itself as the envelope when no wrapper
        # key is present. When we detect that case, preserve a copy under
        # the `hearing` key for forensic output.
        if not isinstance(env, dict) and any(
            k in values for k in ("committees", "dates", "title", "formats")
        ):
            env = values
            # Preserve the original envelope as a shallow copy so we don't
            # keep a self-referential structure.
            if "hearing" not in values:
                values["hearing"] = dict(values)
        if isinstance(env, dict):
            # Title
            if not values.get("title") and env.get("title"):
                values["title"] = env.get("title")

            # URL (prefer explicit top-level, otherwise formats/url)
            if not values.get("url") and env.get("url"):
                values["url"] = env.get("url")

            # Chamber
            if not values.get("chamber") and env.get("chamber"):
                values["chamber"] = env.get("chamber")

            # Committee name: prefer first committee entry
            if not values.get("committee_name"):
                # Support either a `committee` object or `committees` list
                if isinstance(env.get("committee"), dict) and env.get(
                    "committee", {}
                ).get("name", ""):
                    values["committee_name"] = env.get("committee", {}).get("name")
                elif isinstance(env.get("committees"), list) and env.get("committees"):
                    first = env.get("committees", [])[0]
                    if isinstance(first, dict) and first.get("name", ""):
                        values["committee_name"] = first.get("name")

            # Normalize committee system id keys so downstream code can
            # reliably access either `systemCode` or `system_code`.
            if isinstance(env.get("committees"), list):
                normalized_committees = []
                for sc in env.get("committees", []):
                    if isinstance(sc, dict):
                        if sc.get("systemCode") and not sc.get("system_code"):
                            sc["system_code"] = sc.get("systemCode")
                        if sc.get("system_code") and not sc.get("systemCode"):
                            sc["systemCode"] = sc.get("system_code")
                    normalized_committees.append(sc)
                values["committees"] = normalized_committees

            # Hearing date: prefer first `dates` entry, but accept singular `date` or `hearingDate` keys
            if not values.get("hearing_date"):
                if isinstance(env.get("dates"), list) and env.get("dates"):
                    first = env.get("dates", [])[0]
                    if isinstance(first, dict) and first.get("date"):
                        values["hearing_date"] = first.get("date")
                elif env.get("date"):
                    values["hearing_date"] = env.get("date")
                elif env.get("hearingDate"):
                    values["hearing_date"] = env.get("hearingDate")

            # Jacket number and other numeric fields are preserved in the envelope
        return values

    @field_validator("chamber", mode="before")
    def _normalize_chamber(cls, v):
        """Normalize chamber values like 'NoChamber' into a `Chamber` or None."""
        return normalize_chamber(v)


class BehalfType(StrEnum):
    """Enumeration for on-behalf-of sponsorship types."""

    # This can be "Submitted on behalf of" the sponsor and/or "Proposed on behalf of" the sponsor. Assign value based on first word of input
    SUBMITTED = "Submitted"
    PROPOSED = "Proposed"

    @property
    def type_url(self):
        """Return the URL-friendly token for the behalf type."""
        return self.value.split()[0]


class AmendmentType(StrEnum):
    """Enumeration of amendment types by chamber and numbering scheme."""

    SAMDT = "SAMDT"  # Senate Amendment
    HAMDT = "HAMDT"  # House Amendment
    SUAMDT = "SUAMDT"  # Senate Unnumbered Amendment

    def __init__(self, value: str):
        """Initialize the enum and cache the URL-friendly slug."""
        self._value_ = value
        self.type_url = value.lower()


class TextVersion(BaseModel):
    """Text version for a bill or amendment, including formats and publish date."""

    date: Annotated[datetime, Field(description="When the text version was published.")]
    formats: Annotated[
        List[Format], Field(description="Which formats are available for this text.")
    ]
    type: Annotated[str, Field(description="What type of text version this is.")]


class BillTextResponse(BaseModel):
    """Response wrapper for bill text endpoints (list of text versions)."""

    pagination: Annotated[
        Optional[dict],
        Field(default=None, description="Pagination metadata if present"),
    ] = None
    request: Annotated[
        Optional[dict], Field(default=None, description="Original request metadata")
    ] = None
    textVersions: Annotated[
        List[TextVersion], Field(description="List of available text versions")
    ] = []


class PolicyArea(BaseModel):
    """Policy area classification assigned to a bill."""

    name: Annotated[str, Field(description="What the policy area name is.")]
    update_date: Annotated[
        Optional[datetime],
        Field(alias="updateDate", description="When the policy area was last updated."),
    ] = None


class LegislativeSubject(BaseModel):
    """Legislative subject classification assigned to a bill."""

    name: Annotated[str, Field(description="What the legislative subject name is.")]
    update_date: Annotated[
        Optional[datetime],
        Field(alias="updateDate", description="When the subject was last updated."),
    ] = None


class LawType(StrEnum):
    """Enumeration of law types with API slug helpers."""

    PUBLIC = "Public Law"
    PRIVATE = "Private Law"

    def __init__(self, value: str):
        """Initialize the enum and derive the API slug for the law type."""
        self._value_ = value
        if value == "Public Law":
            self.type_url = "pub"
        elif value == "Private Law":
            self.type_url = "priv"


class LatestAction(BaseModel):
    """Latest action metadata with date and action text."""

    action_date: Annotated[
        Optional[datetime],
        Field(alias="actionDate", description="When the latest action occurred."),
    ] = None
    text: Annotated[str, Field(description="What the latest action text says.")]


class Summary(BaseModel):
    """Bill summary metadata including action and version information."""

    action_date: Annotated[
        datetime,
        Field(alias="actionDate", description="When the summary action occurred."),
    ]
    action_desc: Annotated[
        str, Field(alias="actionDesc", description="What the summary action describes.")
    ]
    text: Annotated[str, Field(description="What the summary text says.")]
    updateDate: Annotated[
        datetime,
        Field(alias="updateDate", description="When the summary was last updated."),
    ]
    version_code: Annotated[
        str, Field(alias="versionCode", description="Which summary version this is.")
    ]


class ActionSourceSystem(StrEnum):
    """Enumeration of source system codes for actions."""

    SENATE = "0"
    LIBRARY_OF_CONGRESS = "9"
    HOUSE1 = "1"
    HOUSE2 = "2"


class IdentifyingEntity(StrEnum):
    """Enumeration of entities that identify relationships between bills."""

    HOUSE = "House"
    SENATE = "Senate"
    CRS = "CRS"  # Congressional Research Service


class RelationshipDetail(BaseModel):
    """Details describing how a relationship between bills was identified."""

    identified_by: Annotated[
        Optional[IdentifyingEntity],
        Field(alias="identifiedBy", description="Who identified the relationship."),
    ] = None
    type: Annotated[str, Field(description="What type of relationship this is.")]


class ChamberCode(StrEnum):
    """Chamber code values used in API responses."""

    house = "H"
    senate = "S"


class BillType(StrEnum):
    """Enumeration of bill types with API slug helpers."""

    def __init__(self, value: str):
        """Initialize the enum and cache a URL-friendly slug.

        Args:
            value: The enum's string value (e.g., 'HR', 'S').
        """
        self._value_ = value
        self.type_url = value.lower()

    HR = "HR"  # Bill introduced in House
    S = "S"  # Bill introduced in Senate
    HJRES = "HJRES"  # Joint resolution introduced in House
    SJRES = "SJRES"  # Joint resolution introduced in Senate
    HCONRES = "HCONRES"  # Concurrent resolution introduced in House
    SCONRES = "SCONRES"  # Concurrent resolution introduced in Senate
    HRES = "HRES"  # Simple resolution introduced in House
    SRES = "SRES"  # Simple resolution introduced in Senate


class LawMetadata(BaseModel):
    """Law metadata attached to a bill (law number and type)."""

    number: Annotated[str, Field(description="What the law number is.")]
    law_type: Annotated[
        LawType, Field(alias="type", description="What type of law this is.")
    ]

    @field_validator("law_type", mode="before")
    def convert_law_type(cls, value: str):
        """Field validator to coerce incoming law type strings.

        Accepts values like 'Public Law' or 'Private Law' and returns the
        corresponding ``LawType`` enum via the shared ``convert_law_type``
        helper. This runs in ``before`` mode to allow string inputs.

        Args:
            value: Incoming raw value for the ``law_type`` field.

        Returns:
            Converted enum value accepted by the field.
        """
        return convert_law_type(value)


# General Committee model (API entity)
class Committee(BaseModel):
    """Committee entity with activities and subcommittee hierarchy."""

    name: Annotated[str, Field(description="What the committee name is.")]
    chamber: Annotated[
        Optional[str], Field(description="Which chamber the committee belongs to.")
    ] = None
    type: Annotated[
        Optional[str], Field(description="What type of committee this is.")
    ] = None
    system_code: Annotated[
        str, Field(alias="systemCode", description="What the committee system code is.")
    ]
    url: Annotated[
        HttpUrl, Field(description="Where to retrieve the committee in the API.")
    ]
    # Preserve historical activity list when present in API responses
    history: Annotated[
        List[dict],
        Field(
            default_factory=list, description="Historical snapshots of the committee"
        ),
    ] = []
    # Present in some API responses
    is_current: Annotated[
        Optional[bool],
        Field(
            alias="isCurrent",
            default=None,
            description="Whether this committee is current",
        ),
    ] = None
    update_date: Annotated[
        Optional[datetime],
        Field(
            alias="updateDate",
            default=None,
            description="When committee was last updated",
        ),
    ] = None
    activities: Annotated[
        List[Activity],
        Field(description="Which activities are recorded for the committee."),
    ] = []
    subcommittees: Annotated[
        List["Committee"],
        Field(description="Which subcommittees belong to the committee."),
    ] = []

    # Preserve additional API-provided fields that are not always present.
    # Some endpoints return these as either a list of items or a count/url wrapper
    # object (e.g. {"count":0, "url":"..."}). Accept both shapes.
    bills: Annotated[
        Optional[CountUrl],
        Field(
            default=None,
            description="Bills associated with the committee as provided by the API (CountUrl envelope)",
        ),
    ] = None
    committee_website_url: Annotated[
        Optional[HttpUrl],
        Field(
            alias="committeeWebsiteUrl",
            default=None,
            description="Committee website URL as provided by the API",
        ),
    ] = None
    communications: Annotated[
        Optional[CountUrl],
        Field(
            default=None,
            description="Communications associated with the committee (CountUrl envelope)",
        ),
    ] = None
    nominations: Annotated[
        Optional[CountUrl],
        Field(
            default=None,
            description="Nominations associated with the committee (CountUrl envelope)",
        ),
    ] = None
    parent: Annotated[
        Optional[dict],
        Field(
            default=None,
            description="Parent committee object when present in API responses",
        ),
    ] = None
    reports: Annotated[
        Optional[CountUrl],
        Field(
            default=None,
            description="Reports associated with the committee (CountUrl envelope)",
        ),
    ] = None

    def __init__(self, **data):
        """Initialize committee and normalize nested subcommittee objects."""
        super().__init__(**data)
        # Ensure subcommittees are Committee instances
        self.subcommittees = [
            Committee(**sc) if isinstance(sc, dict) else sc for sc in self.subcommittees
        ]

    @model_validator(mode="before")
    def _normalize_api_payload(cls, values: dict):
        """Normalize common API shapes into the Committee model's expected fields.

        - Extract a human-friendly `name` from `history[0].officialName` or
          `history[0].libraryOfCongressName` when `name` is not provided.
        - Populate `chamber` from `type` when absent.
        - Ensure a canonical `url` exists by combining `chamber` and `systemCode`.
        This keeps endpoint-specific shaping colocated with the model that
        consumes it while avoiding client-level special casing.
        """
        if not values.get("name"):
            hist = values.get("history")
            if isinstance(hist, list) and hist:
                first = hist[0]
                if isinstance(first, dict):
                    name = first.get("officialName") or first.get(
                        "libraryOfCongressName"
                    )
                    if name:
                        values["name"] = name

        if not values.get("chamber"):
            t = values.get("type")
            if isinstance(t, str):
                values["chamber"] = t

        if not values.get("url"):
            system_code = values.get("systemCode") or values.get("system_code")
            # Ensure canonical internal key exists for downstream code
            if system_code and not values.get("system_code"):
                values["system_code"] = system_code
            chamber = values.get("chamber") or (
                values.get("type") if isinstance(values.get("type"), str) else None
            )
            if system_code and chamber:
                values["url"] = (
                    f"https://api.congress.gov/v3/committee/{str(chamber).lower()}/{system_code}"
                )
        # Ensure nested subcommittee entries are normalized to include at least
        # a chamber, type, systemCode (or system_code), and url so that
        # constructing Committee(**subcommittee_dict) doesn't fail when the
        # API returns minimal subcommittee objects (e.g. only name/url).
        parent_chamber = values.get("chamber")
        parent_type = values.get("type")
        subs = values.get("subcommittees")
        if isinstance(subs, list) and subs:
            normalized = []
            for sc in subs:
                if not isinstance(sc, dict):
                    normalized.append(sc)
                    continue
                # Fill missing chamber/type from parent if available
                if not sc.get("chamber") and parent_chamber:
                    sc["chamber"] = parent_chamber
                if not sc.get("type") and parent_type:
                    sc["type"] = parent_type
                # Accept either systemCode or system_code
                # Accept either systemCode or system_code and normalize both
                if sc.get("systemCode") and not sc.get("system_code"):
                    sc["system_code"] = sc.get("systemCode")
                if sc.get("system_code") and not sc.get("systemCode"):
                    sc["systemCode"] = sc.get("system_code")
                # If url missing but we have chamber and a system id, construct it
                system_id = sc.get("systemCode") or sc.get("system_code")
                if not sc.get("url") and system_id and sc.get("chamber"):
                    sc["url"] = (
                        f"https://api.congress.gov/v3/committee/{str(sc.get('chamber')).lower()}/{system_id}"
                    )
                normalized.append(sc)
            values["subcommittees"] = normalized
        # Coerce CountUrl-shaped dicts into `CountUrl` instances for the
        # fields that the API represents as envelopes. If other shapes
        # appear, leave them so validation can surface unexpected cases.
        for envelope_field in ("bills", "communications", "nominations", "reports"):
            val = values.get(envelope_field)
            if isinstance(val, dict) and set(["count", "url"]).issubset(
                set(val.keys())
            ):
                try:
                    values[envelope_field] = CountUrl(**val)
                except Exception:
                    # fall through and leave original shape — downstream code
                    # will surface a validation error if it's truly invalid
                    pass
        return values


# Metadata-only model for committee lists
class CommitteeMetadata(BaseModel):
    """List-level committee metadata used in related records."""

    activities: Annotated[
        List[Activity],
        Field(description="Which activities are recorded for the committee."),
    ]
    chamber: Annotated[
        str, Field(description="Which chamber the committee belongs to.")
    ]
    name: Annotated[str, Field(description="What the committee name is.")]
    system_code: Annotated[
        str, Field(alias="systemCode", description="What the committee system code is.")
    ]
    type: Annotated[str, Field(description="What type of committee this is.")]
    url: Annotated[
        HttpUrl, Field(description="Where to retrieve the committee in the API.")
    ]


class RecordedVote(BaseModel):
    """Recorded vote metadata tied to actions or roll calls."""

    roll_number: Annotated[
        int, Field(alias="rollNumber", description="What the roll call number is.")
    ]
    url: Annotated[HttpUrl, Field(description="Where to retrieve the vote in the API.")]
    chamber: Annotated[
        Chamber, Field(alias="chamber", description="Which chamber held the vote.")
    ]
    congress: Annotated[int, Field(description="Which Congress the vote belongs to.")]
    date: Annotated[datetime, Field(description="When the vote occurred.")]
    session_number: Annotated[
        int,
        Field(alias="sessionNumber", description="Which session the vote occurred in."),
    ]


class Action(BaseModel):
    """Action entry for a bill or amendment, including timing and committees."""

    action_date: Annotated[
        Optional[datetime],
        Field(alias="actionDate", description="When the action occurred."),
    ] = None
    action_code: Annotated[
        str, Field(alias="actionCode", description="What the action code is.")
    ] = ""
    source_system: Annotated[
        Optional[SourceSystem],
        Field(alias="sourceSystem", description="Which system provided the action."),
    ] = None
    text: Annotated[str, Field(description="What the action text says.")]
    type: Annotated[str | None, Field(description="What type of action this is.")] = ""
    committees: Annotated[
        Optional[List[CommitteeMetadata]],
        Field(description="Which committees are associated with the action."),
    ] = []
    action_time: Annotated[
        Optional[datetime],
        Field(alias="actionTime", description="What time the action occurred."),
    ] = None
    recorded_votes: Annotated[
        List[RecordedVote],
        Field(
            alias="recordedVotes",
            description="Which recorded votes are tied to the action.",
        ),
    ] = []


class AmendmentMetadata(BaseModel):
    """List-level metadata describing an amendment reference."""

    congress: Annotated[
        int, Field(description="Which Congress the amendment belongs to.")
    ]
    latest_action: Annotated[
        Optional[LatestAction],
        Field(alias="latestAction", description="What the latest action is."),
    ] = None
    number: Annotated[int, Field(description="What the amendment number is.")]
    purpose: Annotated[str, Field(description="What purpose the amendment states.")]
    type: Annotated[str, Field(description="What type of amendment this is.")]
    update_date: Annotated[
        datetime,
        Field(alias="updateDate", description="When the amendment was last updated."),
    ]
    url: Annotated[
        HttpUrl, Field(description="Where to retrieve the amendment in the API.")
    ]


class Treaty(BaseModel):
    """Treaty reference used in amendment or bill metadata."""

    congress: Annotated[int, Field(description="Which Congress the treaty belongs to.")]
    treaty_number: Annotated[
        str, Field(alias="treatyNumber", description="What the treaty number is.")
    ]
    url: Annotated[
        HttpUrl, Field(description="Where to retrieve the treaty in the API.")
    ]


class Subjects(BaseModel):
    """Subject bundle containing legislative subjects and policy area."""

    legislative_subjects: Annotated[
        List[LegislativeSubject],
        Field(
            alias="legislativeSubjects", description="Which legislative subjects apply."
        ),
    ] = []
    policy_area: Annotated[
        PolicyArea, Field(alias="policyArea", description="What the policy area is.")
    ]


class BillMetadata(EntityBase):
    """List-level bill metadata used for related bill references."""

    congress: Annotated[int, Field(description="Which Congress the bill belongs to.")]
    latest_action: Annotated[
        Optional[LatestAction],
        Field(alias="latestAction", description="What the latest action is."),
    ] = None
    number: Annotated[int, Field(description="What the bill number is.")]
    relationship_details: Annotated[
        List[RelationshipDetail],
        Field(
            alias="relationshipDetails",
            description="What relationship details are recorded.",
        ),
    ] = []
    title: Annotated[str, Field(description="What the bill title is.")]
    type: Annotated[str, Field(description="What type of bill this is.")]
    url: Annotated[HttpUrl, Field(description="Where to retrieve the bill in the API.")]

    origin_chamber: Annotated[
        Optional[str],
        Field(alias="originChamber", description="Origin chamber name for the bill."),
    ] = None

    origin_chamber_code: Annotated[
        Optional[str],
        Field(alias="originChamberCode", description="Origin chamber short code."),
    ] = None

    update_date_including_text: Annotated[
        Optional[str],
        Field(
            alias="updateDateIncludingText",
            description="Update date including text availability.",
        ),
    ] = None

    @model_validator(mode="after")
    def _populate_id_if_missing(cls, model):
        """Ensure a deterministic `id` is present when possible."""
        try:
            if not getattr(model, "id", None):
                model.id = model.build_id()
        except Exception:
            # best-effort: do not fail validation on id build failure
            pass
        return model

    def build_id(self) -> str:
        """Return a canonical id for this bill metadata entry.

        Prefer explicit congress/type/number composition; fall back to
        parsing the URL. Raises ValueError when an id cannot be constructed.
        """
        congress = getattr(self, "congress", None)
        bill_type = getattr(self, "type", None)
        number = getattr(self, "number", None)
        if congress and bill_type and number:
            try:
                t = str(bill_type).lower()
            except Exception:
                t = "bill"
            return f"bill:{congress}:{t}:{number}"
        # fallback: try to parse URL into an id
        from src.data_collection.id_utils import parse_url_to_id

        url = getattr(self, "url", None)
        if url:
            return parse_url_to_id(str(url))
        raise ValueError(
            "Could not build canonical id for BillMetadata: missing congress/type/number/url"
        )


class Amendment(BaseModel):
    """Amendment record with sponsors, actions, and text versions."""

    # Fields added by collecting additional data with client object
    actions: Annotated[
        Optional[Union[List[Action], "CountUrl"]],
        Field(description="Which actions are associated with the amendment."),
    ] = None
    cosponsors: Annotated[
        Optional[Union[List[Member], "CountUrl"]],
        Field(description="Which members cosponsored the amendment."),
    ] = None
    text_versions: Annotated[
        Optional[Union[List[TextVersion], "CountUrl"]],
        Field(
            alias="textVersions",
            description="Which text versions are available for the amendment.",
        ),
    ] = None
    # Normal fields
    congress: Annotated[
        int, Field(description="Which Congress the amendment belongs to.")
    ]
    description: Annotated[
        Optional[str], Field(description="What the amendment description says.")
    ] = None
    purpose: Annotated[
        Optional[str], Field(description="What purpose the amendment states.")
    ] = None
    latest_action: Annotated[
        Optional[LatestAction],
        Field(alias="latestAction", description="What the latest action is."),
    ] = None
    number: Annotated[int, Field(description="What the amendment number is.")]
    type: Annotated[str, Field(description="What type of amendment this is.")]
    update_date: Annotated[
        datetime,
        Field(alias="updateDate", description="When the amendment was last updated."),
    ]
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the amendment in the API."),
    ] = None
    sponsors: Annotated[
        List[Union[Member, SponsorRef]],
        Field(description="Which members or refs sponsored the amendment."),
    ] = []
    on_behalf_of_sponsor: Annotated[
        Optional[Member],
        Field(
            alias="onBehalfOfSponsor",
            description="Who introduced the amendment on behalf of the sponsor.",
        ),
    ] = None
    behalf_type: Annotated[
        Optional[BehalfType],
        Field(
            alias="behalfType",
            description="What type of on-behalf-of sponsorship applies.",
        ),
    ] = None
    proposed_date: Annotated[
        Optional[datetime],
        Field(alias="proposedDate", description="When the amendment was proposed."),
    ] = None
    submitted_date: Annotated[
        Optional[datetime],
        Field(alias="submittedDate", description="When the amendment was submitted."),
    ] = None
    chamber: Annotated[
        Optional[Chamber],
        Field(
            alias="chamber",
            description="Which chamber the amendment is associated with.",
        ),
    ] = None

    @field_validator("chamber", mode="before")
    def _normalize_chamber(cls, v):
        """Normalize slightly different chamber strings into the `Chamber` enum.

        Accepts values like 'House of Representatives', 'house', 'H', 'Senate',
        'S', and various casing/abbreviations and returns a `Chamber` value.
        """
        return normalize_chamber(v)

    @field_validator("number", mode="before")
    def _coerce_number_to_int(cls, v):
        if v is None:
            return v
        try:
            return int(v)
        except Exception:
            return v

    amended_bill: Annotated[
        Optional["BillMetadata"],
        Field(alias="amendedBill", description="Which bill is amended, if applicable."),
    ] = None

    links: Annotated[
        Optional[List[dict]],
        Field(alias="links", description="Related links associated with the amendment."),
    ] = None
    full_text: Annotated[str, Field(description="What the full amendment text is.")] = (
        ""
    )

    def add_full_text(self, client: CDGClient) -> str:
        """Fetch and return the full amendment text from formatted text versions."""
        import requests

        if not self.text_versions or not isinstance(self.text_versions, list):
            return ""

        for text_version in self.text_versions:
            formats = getattr(text_version, "formats", []) or []
            for fmt in formats:
                ftype = getattr(fmt, "type", "")
                if "Formatted" in ftype:
                    try:
                        resp = client.session.get(str(getattr(fmt, "url", "")))
                        html = resp.text
                        soup = BeautifulSoup(html, "html.parser")
                        full_text = soup.get_text()
                    except requests.RequestException as e:
                        raise RuntimeError(
                            f"Network error retrieving full text for text version {self.type}: {e}"
                        ) from e
                    except (AttributeError, TypeError) as e:
                        raise RuntimeError(
                            f"Parsing error for full text in text version {self.type}: {e}"
                        ) from e
                    return full_text
        return ""

    def get_amendment_details(self, client: CDGClient):
        """Populate the amendment with related actions, cosponsors, and text versions."""
        """
        Retrieve additional data for an amendment.

        Args:
            client (CDGClient): The client object.
            amendment_metadata (AmendmentMetadata): The amendment metadata.

        Returns:
            Amendment: The amendment object.
        """
        amendment_data = {}
        congress = self.congress
        amendment_type = self.type
        amendment_number = self.number
        additional_amendment_data = {
            "actions": "actions",
            "cosponsors": "cosponsors",
            "textVersions": "text",
            "amendments": "amendments",
        }

        for key, endpoint in additional_amendment_data.items():
            data = client.get_json(
                f"amendment/{congress}/{amendment_type.lower()}/{amendment_number}/{endpoint}",
                params={"format": None},
            )
            amendment_data[key] = data[key]

        self.actions = [
            Action(**x) for x in amendment_data["actions"] if isinstance(x, dict)
        ]
        self.cosponsors = [
            Member(**x) for x in amendment_data["cosponsors"] if isinstance(x, dict)
        ]
        self.text_versions = [
            TextVersion(**x)
            for x in amendment_data["textVersions"]
            if isinstance(x, dict)
        ]
        self.full_text = self.add_full_text(client)

    def build_id(self) -> str:
        """Return a canonical id for this amendment instance."""
        congress = getattr(self, "congress", None)
        a_type = getattr(self, "type", None)
        number = getattr(self, "number", None)
        if congress and number:
            return f"amendment:{congress}:{str(a_type).lower() if a_type else 'amendment'}:{number}"
        # try parsing URL to derive id, else stable hash fallback
        try:
            url = getattr(self, "url", None)
            if url:
                try:
                    return parse_url_to_id(str(url))
                except Exception as exc:
                    logger.exception("Failed to parse URL to id in build_id: %s", exc)
            mapping = self.model_dump() if hasattr(self, "model_dump") else dict(self)
            return f"record:{abs(hash(str(mapping))) % (10**12)}"
        except Exception:
            return (
                f"record:{abs(hash(str(number or congress or 'amendment'))) % (10**12)}"
            )


class Bill(EntityBase):
    """Bill record with core metadata and optional expanded relationships."""

    # Fields added by collecting additional data with client object
    actions: Annotated[
        Optional[Union[List[Action], "CountUrl"]],
        Field(description="Which actions are associated with the bill."),
    ] = None
    amendments: Annotated[
        Optional[Union[List[Amendment], "CountUrl"]],
        Field(description="Which amendments are associated with the bill."),
    ] = None
    committees: Annotated[
        Optional[Union[List[CommitteeMetadata], "CountUrl"]],
        Field(description="Which committees are associated with the bill."),
    ] = None
    cosponsors: Annotated[
        Optional[Union[List[Sponsor], "CountUrl"]],
        Field(description="Which members cosponsored the bill."),
    ] = None
    related_bills: Annotated[
        Optional[Union[List[BillMetadata], "CountUrl"]],
        Field(
            description="Which related bills are linked to this bill.",
            alias="relatedBills",
        ),
    ] = None
    subjects: Annotated[
        Optional[Union[Subjects, "CountUrl"]],
        Field(description="What subject metadata is available for the bill."),
    ] = None
    summaries: Annotated[
        Optional[Union[List[Summary], "CountUrl"]],
        Field(description="Which summaries are available for the bill."),
    ] = None
    text_versions: Annotated[
        Optional[Union[List[TextVersion], "CountUrl"]],
        Field(
            description="Which text versions are available for the bill.",
            alias="textVersions",
        ),
    ] = None
    titles: Annotated[
        Optional[Union[List[Title], "CountUrl"]],
        Field(description="Which titles are recorded for the bill."),
    ] = None
    full_text: Annotated[str, Field(description="What the full bill text is.")] = ""

    # Fields from original data
    congress: Annotated[int, Field(description="Which Congress the bill belongs to.")]
    constitutional_authority_statement_text: Annotated[
        str,
        Field(
            alias="constitutionalAuthorityStatementText",
            description="What constitutional authority statement is recorded.",
        ),
    ] = ""
    introduced_date: Annotated[
        Optional[datetime],
        Field(alias="introducedDate", description="When the bill was introduced."),
    ] = None
    latest_action: Annotated[
        LatestAction,
        Field(alias="latestAction", description="What the latest action is."),
    ]
    laws: Annotated[
        List[LawMetadata],
        Field(alias="laws", description="Which laws are associated with the bill."),
    ] = []
    number: Annotated[str, Field(description="What the bill number is.")]
    origin_chamber: Annotated[
        Chamber,
        Field(alias="originChamber", description="Which chamber introduced the bill."),
    ]
    origin_chamber_code: Annotated[
        ChamberCode,
        Field(
            alias="originChamberCode", description="What the origin chamber code is."
        ),
    ]
    policy_area: Annotated[
        Optional[PolicyArea],
        Field(
            alias="policyArea",
            description="What policy area the bill is classified under.",
        ),
    ] = None
    sponsors: Annotated[
        Optional[Union[List[Sponsor], "CountUrl"]],
        Field(description="Which members sponsored the bill."),
    ] = None
    title: Annotated[str, Field(description="What the bill title is.")]
    type: Annotated[BillType, Field(description="What type of bill this is.")]
    update_date: Annotated[
        datetime,
        Field(alias="updateDate", description="When the bill was last updated."),
    ]
    update_date_including_text: Annotated[
        datetime,
        Field(
            alias="updateDateIncludingText",
            description="When the bill or its text was last updated.",
        ),
    ]
    notes: Annotated[
        Optional[Union[List[Note], "CountUrl"]],
        Field(alias="notes", description="What notes are attached to the bill."),
    ] = None

    def add_full_text(self, client: CDGClient) -> str:
        """Fetch and return the full bill text from formatted text versions."""
        import requests

        if not self.text_versions or not isinstance(self.text_versions, list):
            return ""

        for text_version in self.text_versions:
            formats = getattr(text_version, "formats", []) or []
            for fmt in formats:
                ftype = getattr(fmt, "type", "")
                if ftype == "Formatted Text":
                    try:
                        resp = client.session.get(str(getattr(fmt, "url", "")))
                        html = resp.text
                        soup = BeautifulSoup(html, "html.parser")
                        full_text = soup.get_text()
                    except requests.RequestException as e:
                        raise RuntimeError(
                            f"Network error retrieving full text for text version {self.type}: {e}"
                        ) from e
                    except (AttributeError, TypeError) as e:
                        raise RuntimeError(
                            f"Parsing error for full text in text version {self.type}: {e}"
                        ) from e
                    return full_text
        return ""

    def add_bill_details(self, client: CDGClient):
        """Populate the bill with related actions, summaries, and linked entities."""
        """
        Retrieve additional data for a bill.

        Args:
            client: A CDGClient object.
        """
        bill_data = {}
        # Currently available endpoints for additional data on bills
        additional_bill_data = {
            "actions": "actions",
            "amendments": "amendments",
            "committees": "committees",
            "cosponsors": "cosponsors",
            "relatedBills": "relatedbills",
            "subjects": "subjects",
            "summaries": "summaries",
            "textVersions": "text",
            "titles": "titles",
        }
        congress = self.congress
        bill_type = self.type.lower()
        bill_number = self.number
        for key, endpoint in additional_bill_data.items():
            data = client.get_json(
                f"bill/{congress}/{bill_type}/{bill_number}/{endpoint}"
            )
            bill_data[key] = data[key]

        self.actions = [
            Action(**x)
            for x in bill_data.get("actions", [])
            if isinstance(bill_data.get("actions"), list)
        ]
        self.amendments = [
            Amendment(**x)
            for x in bill_data.get("amendments", [])
            if isinstance(bill_data.get("amendments"), list)
        ]
        self.cosponsors = [
            Sponsor(**x)
            for x in bill_data.get("cosponsors", [])
            if isinstance(bill_data.get("cosponsors"), list)
        ]
        # relatedBills may be either a list of BillMetadata dicts or a CountUrl-style dict
        rb = bill_data.get("relatedBills")
        if isinstance(rb, dict) and rb.get("count") is not None and rb.get("url"):
            self.related_bills = CountUrl(**rb)
        elif isinstance(rb, list):
            self.related_bills = [BillMetadata(**x) for x in rb]
        else:
            self.related_bills = None
        subjects_data = bill_data["subjects"]
        legislative_subjects = [
            LegislativeSubject(**x)
            for x in subjects_data.get("legislativeSubjects", [])
        ]
        policy_area = (
            PolicyArea(**subjects_data["policyArea"])
            if "policyArea" in subjects_data
            else PolicyArea(name="")
        )
        self.subjects = Subjects(
            legislative_subjects=legislative_subjects, policy_area=policy_area
        )
        self.summaries = [
            Summary(**x)
            for x in bill_data.get("summaries", [])
            if isinstance(bill_data.get("summaries"), list)
        ]
        # textVersions may be a list of TextVersion dicts or a CountUrl dict
        tv = bill_data.get("textVersions")
        if isinstance(tv, dict) and tv.get("count") is not None and tv.get("url"):
            self.text_versions = CountUrl(**tv)
        elif isinstance(tv, list):
            self.text_versions = [TextVersion(**x) for x in tv]
        else:
            self.text_versions = None
        self.titles = [Title(**x) for x in bill_data["titles"]]
        self.full_text = self.add_full_text(client)

    def build_id(self) -> str:
        """Return a canonical id for this bill instance."""
        congress = getattr(self, "congress", None)
        bill_type = getattr(self, "type", None)
        number = getattr(self, "number", None)
        # bill_type may be enum; coerce to str
        if congress and bill_type and number:
            try:
                t = str(bill_type).lower()
            except Exception:
                t = "bill"
            return f"bill:{congress}:{t}:{number}"
        # try parsing URL to derive id, else stable hash fallback
        try:
            from src.data_collection.id_utils import parse_url_to_id

            url = getattr(self, "url", None)
            if url:
                try:
                    return parse_url_to_id(str(url))
                except Exception as exc:
                    logger.exception("Failed to parse URL to id in Bill.build_id: %s", exc)
            mapping = self.model_dump() if hasattr(self, "model_dump") else dict(self)
            return f"record:{abs(hash(str(mapping))) % (10**12)}"
        except Exception:
            return f"record:{abs(hash(str(number or congress or 'bill'))) % (10**12)}"


class Law(Bill):
    """Bill subtype representing an enacted law."""

    is_law: Annotated[
        bool, Field(description="Whether the bill is enacted into law.")
    ] = True


# Committee Report model
class CommitteeReport(EntityBase):
    """Committee report metadata with citation and issuance details."""

    citation: Annotated[
        str, Field(description="What the committee report citation is.")
    ]
    url: Annotated[
        Optional[HttpUrl],
        Field(
            default=None,
            description="Where to retrieve the committee report in the API.",
        ),
    ] = None
    chamber: Annotated[Chamber, Field(description="Which chamber issued the report.")]
    committee_name: Annotated[
        Optional[str], Field(description="Which committee issued the report.")
    ] = None
    report_date: Annotated[
        Optional[datetime], Field(description="When the report was issued.")
    ] = None
    type: Annotated[
        Optional[str], Field(description="What type of report this is.")
    ] = None


# Committee Print model
class CommitteePrint(BaseModel):
    """Committee print metadata with title and issuance details."""

    title: Annotated[str, Field(description="What the committee print title is.")]
    url: Annotated[
        HttpUrl, Field(description="Where to retrieve the committee print in the API.")
    ]
    chamber: Annotated[Chamber, Field(description="Which chamber issued the print.")]
    committee_name: Annotated[
        Optional[str], Field(description="Which committee issued the print.")
    ] = None
    print_date: Annotated[
        Optional[datetime], Field(description="When the print was issued.")
    ] = None
    type: Annotated[
        Optional[str], Field(description="What type of committee print this is.")
    ] = None


# Committee Meeting model
class CommitteeMeeting(BaseModel):
    """Committee meeting metadata with date, chamber, and committee context."""

    name: Annotated[str, Field(description="What the meeting name is.")]
    url: Annotated[
        HttpUrl, Field(description="Where to retrieve the meeting in the API.")
    ]
    chamber: Annotated[Chamber, Field(description="Which chamber held the meeting.")]
    committee_name: Annotated[
        Optional[str], Field(description="Which committee held the meeting.")
    ] = None
    meeting_date: Annotated[
        Optional[datetime], Field(description="When the meeting occurred.")
    ] = None
    type: Annotated[
        Optional[str], Field(description="What type of meeting this is.")
    ] = None


# Response wrapper models for bill sub-endpoints (defined after referenced types)
class BillActionsResponse(BaseModel):
    """Response wrapper for bill actions sub-endpoint.

    Attributes:
        pagination: Optional pagination metadata from the API.
        request: Optional original request metadata.
        actions: List of ``Action`` objects for the bill.
    """

    pagination: Annotated[Optional[dict], Field(default=None)] = None
    request: Annotated[Optional[dict], Field(default=None)] = None
    actions: Annotated[List[Action], Field(default_factory=list)] = Field(
        default_factory=list
    )


class BillAmendmentsResponse(BaseModel):
    """Response wrapper for bill amendments sub-endpoint.

    Attributes:
        pagination: Optional pagination metadata.
        request: Optional original request metadata.
        amendments: List of amendment metadata entries.
    """

    pagination: Annotated[Optional[dict], Field(default=None)] = None
    request: Annotated[Optional[dict], Field(default=None)] = None
    amendments: Annotated[List[AmendmentMetadata], Field(default_factory=list)] = Field(
        default_factory=list
    )


class BillCommitteesResponse(BaseModel):
    """Response wrapper for bill committees sub-endpoint.

    Attributes:
        pagination: Optional pagination metadata.
        request: Optional original request metadata.
        committees: List of committee metadata entries.
    """

    pagination: Annotated[Optional[dict], Field(default=None)] = None
    request: Annotated[Optional[dict], Field(default=None)] = None
    committees: Annotated[List[CommitteeMetadata], Field(default_factory=list)] = Field(
        default_factory=list
    )


class BillCosponsorsResponse(BaseModel):
    """Response wrapper for bill cosponsors sub-endpoint.

    Attributes:
        pagination: Optional pagination metadata.
        request: Optional original request metadata.
        cosponsors: List of sponsor objects.
    """

    pagination: Annotated[Optional[dict], Field(default=None)] = None
    request: Annotated[Optional[dict], Field(default=None)] = None
    cosponsors: Annotated[List[Sponsor], Field(default_factory=list)] = Field(
        default_factory=list
    )


class BillRelatedBillsResponse(BaseModel):
    """Response wrapper for related bills sub-endpoint.

    Attributes:
        pagination: Optional pagination metadata.
        request: Optional original request metadata.
        relatedBills: List of related bill metadata entries.
    """

    pagination: Annotated[Optional[dict], Field(default=None)] = None
    request: Annotated[Optional[dict], Field(default=None)] = None
    relatedBills: Annotated[List[BillMetadata], Field(default_factory=list)] = Field(
        default_factory=list, alias="relatedBills"
    )


class BillSubjectsResponse(BaseModel):
    """Response wrapper for bill subjects sub-endpoint.

    Attributes:
        pagination: Optional pagination metadata.
        request: Optional original request metadata.
        subjects: Optional Subjects object describing classifications.
    """

    pagination: Annotated[Optional[dict], Field(default=None)] = None
    request: Annotated[Optional[dict], Field(default=None)] = None
    subjects: Annotated[Optional[Subjects], Field(default=None)] = None


class BillSummariesResponse(BaseModel):
    """Response wrapper for bill summaries sub-endpoint.

    Attributes:
        pagination: Optional pagination metadata.
        request: Optional original request metadata.
        summaries: List of Summary objects.
    """

    pagination: Annotated[Optional[dict], Field(default=None)] = None
    request: Annotated[Optional[dict], Field(default=None)] = None
    summaries: Annotated[List[Summary], Field(default_factory=list)] = Field(
        default_factory=list
    )


class BillTitlesResponse(BaseModel):
    """Response wrapper for bill titles sub-endpoint.

    Attributes:
        pagination: Optional pagination metadata.
        request: Optional original request metadata.
        titles: List of Title objects for the bill.
    """

    pagination: Annotated[Optional[dict], Field(default=None)] = None
    request: Annotated[Optional[dict], Field(default=None)] = None
    titles: Annotated[List[Title], Field(default_factory=list)] = Field(
        default_factory=list
    )

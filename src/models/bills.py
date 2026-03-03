"""Pydantic models for bills, amendments, laws, committees, and related metadata.

Each model includes per-field descriptions that explain what each attribute answers.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, List, Optional

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, HttpUrl, field_validator

from src.data_collection.client import CDGClient
from src.models.people import Chamber, Member, Sponsor


class Hearing(BaseModel):
    """Hearing metadata with title, chamber, committee, and timing details."""

    title: Annotated[str, Field(description="What the hearing title is.")]
    url: Annotated[
        HttpUrl, Field(description="Where to retrieve the hearing in the API.")
    ]
    chamber: Annotated[Chamber, Field(description="Which chamber held the hearing.")]
    committee_name: Annotated[
        Optional[str], Field(description="Which committee held the hearing.")
    ] = None
    hearing_date: Annotated[
        Optional[datetime], Field(description="When the hearing took place.")
    ] = None
    type: Annotated[
        Optional[str], Field(description="What type of hearing this is.")
    ] = None


class Format(BaseModel):
    """Format metadata for a text version (e.g., PDF, HTML)."""

    type: Annotated[str, Field(description="What format type the text version is.")]
    url: Annotated[
        HttpUrl, Field(description="Where to retrieve the formatted content.")
    ]


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


class Note(BaseModel):
    """Notes container for bill metadata entries."""

    texts: Annotated[
        List[str], Field(alias="text", description="Which note entries are present.")
    ] = []
    text: Annotated[str, Field(description="What the note text is.")] = ""

    def __init__(self, text: str = ""):
        """Initialize a Note with optional text, preserving list aliases."""
        super().__init__(text=text)


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


class SourceSystem(BaseModel):
    """System metadata indicating the source of an action or record."""

    name: Annotated[str, Field(description="What the source system name is.")]
    code: Annotated[int, Field(description="What the source system code is.")] = -1


class ActionSourceSystem(StrEnum):
    """Enumeration of source system codes for actions."""

    SENATE = "0"
    LIBRARY_OF_CONGRESS = "9"
    HOUSE1 = "1"
    HOUSE2 = "2"


class Activity(BaseModel):
    """Committee activity entry with name and date."""

    date: Annotated[
        datetime, Field(description="When the committee activity occurred.")
    ]
    name: Annotated[str, Field(description="What the committee activity name is.")]


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


class CountUrl(BaseModel):
    """Count and URL pair used by list endpoints."""

    count: Annotated[int, Field(description="How many items are available.")]
    url: Annotated[
        HttpUrl, Field(description="Where to retrieve the related list in the API.")
    ]


class Title(BaseModel):
    """Title entry with type, update date, and text version metadata."""

    title: Annotated[str, Field(description="What the title text is.")]
    title_type: Annotated[
        str, Field(alias="titleType", description="What type of title this is.")
    ]
    title_type_code: Annotated[
        int, Field(alias="titleTypeCode", description="What the title type code is.")
    ]
    update_date: Annotated[
        datetime,
        Field(alias="updateDate", description="When the title was last updated."),
    ]
    bill_text_version_code: Annotated[
        str,
        Field(
            alias="billTextVersionCode",
            description="Which bill text version code is referenced.",
        ),
    ] = ""
    bill_text_version_name: Annotated[
        str,
        Field(
            alias="billTextVersionName",
            description="What the bill text version name is.",
        ),
    ] = ""


class ChamberCode(StrEnum):
    """Chamber code values used in API responses."""

    house = "H"
    senate = "S"


class BillType(StrEnum):
    """Enumeration of bill types with API slug helpers."""

    def __init__(self, value: str):
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
        """Convert raw law type strings into the LawType enum."""
        if value == "Public Law":
            return LawType.PUBLIC
        elif value == "Private Law":
            return LawType.PRIVATE
        raise ValueError("Invalid law type")


# General Committee model (API entity)
class Committee(BaseModel):
    """Committee entity with activities and subcommittee hierarchy."""

    name: Annotated[str, Field(description="What the committee name is.")]
    chamber: Annotated[
        str, Field(description="Which chamber the committee belongs to.")
    ]
    type: Annotated[str, Field(description="What type of committee this is.")]
    system_code: Annotated[
        str, Field(alias="systemCode", description="What the committee system code is.")
    ]
    url: Annotated[
        HttpUrl, Field(description="Where to retrieve the committee in the API.")
    ]
    activities: Annotated[
        List[Activity],
        Field(description="Which activities are recorded for the committee."),
    ] = []
    subcommittees: Annotated[
        List["Committee"],
        Field(description="Which subcommittees belong to the committee."),
    ] = []

    def __init__(self, **data):
        """Initialize committee and normalize nested subcommittee objects."""
        super().__init__(**data)
        # Ensure subcommittees are Committee instances
        self.subcommittees = [
            Committee(**sc) if isinstance(sc, dict) else sc for sc in self.subcommittees
        ]


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
    number: Annotated[str, Field(description="What the amendment number is.")]
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


class BillMetadata(BaseModel):
    """List-level bill metadata used for related bill references."""

    congress: Annotated[int, Field(description="Which Congress the bill belongs to.")]
    latest_action: Annotated[
        LatestAction,
        Field(alias="latestAction", description="What the latest action is."),
    ]
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


class Amendment(BaseModel):
    """Amendment record with sponsors, actions, and text versions."""

    # Fields added by collecting additional data with client object
    actions: Annotated[
        List[Action],
        Field(description="Which actions are associated with the amendment."),
    ] = []
    cosponsors: Annotated[
        List[Member], Field(description="Which members cosponsored the amendment.")
    ] = []
    text_versions: Annotated[
        List[TextVersion],
        Field(description="Which text versions are available for the amendment."),
    ] = []
    # Normal fields
    congress: Annotated[
        int, Field(description="Which Congress the amendment belongs to.")
    ]
    description: Annotated[
        str, Field(description="What the amendment description says.")
    ]
    purpose: Annotated[str, Field(description="What purpose the amendment states.")]
    latest_action: Annotated[
        Optional[LatestAction],
        Field(alias="latestAction", description="What the latest action is."),
    ] = None
    number: Annotated[str, Field(description="What the amendment number is.")]
    type: Annotated[str, Field(description="What type of amendment this is.")]
    update_date: Annotated[
        datetime,
        Field(alias="updateDate", description="When the amendment was last updated."),
    ]
    url: Annotated[
        HttpUrl, Field(description="Where to retrieve the amendment in the API.")
    ]
    sponsors: Annotated[
        List[Member], Field(description="Which members sponsored the amendment.")
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
    amended_treaty: Annotated[
        Optional[Treaty],
        Field(
            alias="amendedTreaty", description="Which treaty is amended, if applicable."
        ),
    ] = None
    full_text: Annotated[str, Field(description="What the full amendment text is.")] = (
        ""
    )

    def add_full_text(self, client: CDGClient) -> str:
        """Fetch and return the full amendment text from formatted text versions."""
        import requests

        for text_version in self.text_versions:
            for format in text_version.formats:
                if "Formatted" in format.type:
                    try:
                        html = client.get(str(format.url))
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
            data = client.get(
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


class Bill(BaseModel):
    """Bill record with core metadata and optional expanded relationships."""

    # Fields added by collecting additional data with client object
    actions: Annotated[
        List[Action], Field(description="Which actions are associated with the bill.")
    ] = []
    amendments: Annotated[
        List[Amendment],
        Field(description="Which amendments are associated with the bill."),
    ] = []
    committees: Annotated[
        List[CommitteeMetadata],
        Field(description="Which committees are associated with the bill."),
    ] = []
    cosponsors: Annotated[
        List[Sponsor], Field(description="Which members cosponsored the bill.")
    ] = []
    related_bills: Annotated[
        List[BillMetadata],
        Field(description="Which related bills are linked to this bill."),
    ] = []
    subjects: Annotated[
        Subjects, Field(description="What subject metadata is available for the bill.")
    ]
    summaries: Annotated[
        List[Summary], Field(description="Which summaries are available for the bill.")
    ] = []
    text_versions: Annotated[
        List[TextVersion],
        Field(description="Which text versions are available for the bill."),
    ] = []
    titles: Annotated[
        List[Title], Field(description="Which titles are recorded for the bill.")
    ] = []
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
        List[Sponsor], Field(description="Which members sponsored the bill.")
    ] = []
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
        Optional[Note],
        Field(alias="notes", description="What notes are attached to the bill."),
    ] = None

    def add_full_text(self, client: Any) -> str:
        """Fetch and return the full bill text from formatted text versions."""
        import requests

        for text_version in self.text_versions:
            for format in text_version.formats:
                if format.type == "Formatted Text":
                    try:
                        html = client.get(format.url)
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
            data = client.get(f"bill/{congress}/{bill_type}/{bill_number}/{endpoint}")
            bill_data[key] = data[key]

        self.actions = [Action(**x) for x in bill_data["actions"]]
        self.amendments = [Amendment(**x) for x in bill_data["amendments"]]
        self.cosponsors = [Sponsor(**x) for x in bill_data["cosponsors"]]
        self.related_bills = [BillMetadata(**x) for x in bill_data["relatedBills"]]
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
        self.summaries = [Summary(**x) for x in bill_data["summaries"]]
        self.text_versions = [TextVersion(**x) for x in bill_data["textVersions"]]
        self.titles = [Title(**x) for x in bill_data["titles"]]
        self.full_text = self.add_full_text(client)


class Law(Bill):
    """Bill subtype representing an enacted law."""

    is_law: Annotated[
        bool, Field(description="Whether the bill is enacted into law.")
    ] = True


# Committee Report model
class CommitteeReport(BaseModel):
    """Committee report metadata with citation and issuance details."""

    citation: Annotated[
        str, Field(description="What the committee report citation is.")
    ]
    url: Annotated[
        HttpUrl, Field(description="Where to retrieve the committee report in the API.")
    ]
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

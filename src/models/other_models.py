"""Additional Pydantic models for list items, auxiliary entities, and parameters.

Each model includes per-field descriptions that explain what each attribute answers.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, List, Optional

from pydantic import BaseModel, Field, HttpUrl, model_validator
import logging

logger = logging.getLogger(__name__)
from src.models.shared import EntityBase, Format, CountUrl


class RecordTypeBase(BaseModel):
    """Base model that carries the knowledgebase record type."""

    recordType: Annotated[
        str, Field(description="Which knowledgebase index this record belongs to.")
    ] = ""


class Subject(BaseModel):
    """Structured subject label with optional update timing."""

    name: Annotated[str, Field(description="What the subject name is.")]
    update_date: Annotated[
        Optional[datetime], Field(description="When the subject was last updated.")
    ] = None


class Topic(BaseModel):
    """Structured topic label with optional update timing."""

    topic: Annotated[str, Field(description="What the topic label is.")]
    update_date: Annotated[
        Optional[datetime], Field(description="When the topic was last updated.")
    ] = None


class HouseCommunication(EntityBase):
    """House communication record with sender, recipient, and subject."""

    # Include identifier fields so `build_id()` can compose a canonical id
    congress: Annotated[
        Optional[int], Field(description="Which Congress the communication belongs to.")
    ] = None
    number: Annotated[
        Optional[int], Field(description="What the communication number is.")
    ] = None
    chamber: Annotated[
        Optional[str], Field(description="Which chamber sent the communication.")
    ] = None

    type: Annotated[
        Optional[str], Field(description="What type of communication this is.")
    ] = None
    # Preserve raw API fields commonly returned in the `houseCommunication` envelope
    abstract: Annotated[
        Optional[str],
        Field(
            default=None, description="Raw abstract text from the API", alias="abstract"
        ),
    ] = None
    committees: Annotated[
        Optional[List[dict]],
        Field(
            default=None,
            description="Raw committee objects from the API",
            alias="committees",
        ),
    ] = None
    communicationType: Annotated[
        Optional["CommunicationTypeInfo"],
        Field(
            default=None,
            description="Raw communicationType envelope",
            alias="communicationType",
        ),
    ] = None
    congressional_record_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="congressionalRecordDate",
            description="Congressional Record date associated with this communication",
        ),
    ] = None
    is_rulemaking: Annotated[
        Optional[bool],
        Field(
            default=None,
            alias="isRulemaking",
            description="Whether the item is rulemaking; API may return string or bool.",
        ),
    ] = None
    report_nature: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="reportNature",
            description="Human-readable description of the report nature when present.",
        ),
    ] = None
    session_number: Annotated[
        Optional[int],
        Field(
            default=None,
            alias="sessionNumber",
            description="Which session number the record belongs to.",
        ),
    ] = None
    date: Annotated[
        Optional[datetime], Field(description="When the communication was submitted.")
    ] = None
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the communication record in the API."),
    ] = None
    subject: Annotated[
        Optional[Subject], Field(description="What subject the communication concerns.")
    ] = None
    sender: Annotated[
        Optional[str], Field(description="Who sent the communication.")
    ] = None
    recipient: Annotated[
        Optional[str], Field(description="Who received the communication.")
    ] = None

    @model_validator(mode="before")
    def _populate_type_from_comm_type(cls, values: dict):
        # Accept `communicationType` object from API and map to `type` string
        ct = values.get("communicationType")
        if (not values.get("type")) and isinstance(ct, dict):
            # prefer human-readable name, fallback to code
            values["type"] = ct.get("name") or ct.get("code")
        return values

    @model_validator(mode="before")
    def _normalize_house_communication(cls, values: dict):
        # Map API keys to our model fields when present
        # abstract -> subject.name (keep abstract as a preserved field too)
        abstract = values.get("abstract")
        if abstract and not values.get("subject"):
            subj = {"name": abstract}
            # also preserve potential congress record date as subject.update_date
            if values.get("congressionalRecordDate"):
                subj["update_date"] = values.get("congressionalRecordDate")
            values["subject"] = subj

        # Prefer explicit date fields from the API if model `date` is missing
        if not values.get("date"):
            if values.get("updateDate"):
                values["date"] = values.get("updateDate")
            elif values.get("congressionalRecordDate"):
                values["date"] = values.get("congressionalRecordDate")

        # Copy congressionalRecordDate into our snake_case field for preservation
        if values.get("congressionalRecordDate") and not values.get(
            "congressional_record_date"
        ):
            values["congressional_record_date"] = values.get("congressionalRecordDate")

        # Sender: prefer submittingOfficial, fallback to submittingAgency
        if not values.get("sender"):
            so = values.get("submittingOfficial") or values.get("submittingAgency")
            if so:
                values["sender"] = so

        # Recipient: default to first committee name when present
        if not values.get("recipient"):
            comms = values.get("committees")
            if isinstance(comms, list) and comms:
                first = comms[0]
                if isinstance(first, dict) and first.get("name"):
                    values["recipient"] = first.get("name")

        # Normalize committees entries to ensure `system_code`/`systemCode` both available
        if isinstance(values.get("committees"), list):
            normalized = []
            for c in values.get("committees", []):
                if isinstance(c, dict):
                    if c.get("systemCode") and not c.get("system_code"):
                        c["system_code"] = c.get("systemCode")
                    if c.get("system_code") and not c.get("systemCode"):
                        c["systemCode"] = c.get("system_code")
                normalized.append(c)
            values["committees"] = normalized

        # URL: if present in API, keep it (some item payloads omit it)
        # leave `url` alone if already provided

        # Build a canonical id when possible from congress/number/chamber
        if not values.get("id"):
            congress = values.get("congress")
            number = values.get("number")
            chamber = values.get("chamber")
            if congress is not None and number is not None:
                # follow list id format: house_communications:119:House:3001
                resource = "house_communications"
                if chamber:
                    values["id"] = f"{resource}:{congress}:{chamber}:{number}"
                else:
                    values["id"] = f"{resource}:{congress}:{number}"

        # Construct a reasonable item `url` when API omits it but we have path parts
        if not values.get("url"):
            congress = values.get("congress")
            number = values.get("number")
            comm_type = None
            ct = values.get("communicationType")
            if isinstance(ct, dict):
                comm_type = ct.get("code") or ct.get("name")
            if congress is not None and number is not None and comm_type:
                try:
                    code = str(comm_type).lower()
                    values["url"] = (
                        f"https://api.congress.gov/v3/house-communication/{congress}/{code}/{number}?format=json"
                    )
                except Exception as exc:
                    logger.exception(
                        "Failed to construct house communication URL: %s", exc
                    )

        # Preserve camelCase fields into snake_case aliases when appropriate
        if values.get("updateDate") and not values.get("update_date"):
            values["update_date"] = values.get("updateDate")
        if values.get("sessionNumber") and not values.get("session_number"):
            values["session_number"] = values.get("sessionNumber")
        if values.get("reportNature") and not values.get("report_nature"):
            values["report_nature"] = values.get("reportNature")

        # Coerce isRulemaking which may be returned as string "True"/"False"
        ir = values.get("isRulemaking")
        if ir is not None and values.get("is_rulemaking") is None:
            if isinstance(ir, bool):
                values["is_rulemaking"] = ir
            elif isinstance(ir, str):
                values["is_rulemaking"] = ir.lower() in ("true", "1", "yes")

        return values


class HouseRequirement(EntityBase):
    """House requirement record describing a required submission or report."""

    type: Annotated[str, Field(description="What type of requirement this is.")]
    description: Annotated[
        Optional[str], Field(description="What the requirement describes.")
    ] = None
    date: Annotated[
        Optional[datetime], Field(description="When the requirement was recorded.")
    ] = None
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the requirement record in the API."),
    ] = None


class SenateCommunication(EntityBase):
    """Senate communication record with sender, recipient, and subject."""

    type: Annotated[
        Optional[str], Field(description="What type of communication this is.")
    ] = None
    date: Annotated[
        Optional[datetime], Field(description="When the communication was submitted.")
    ] = None
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the communication record in the API."),
    ] = None
    subject: Annotated[
        Optional[Subject], Field(description="What subject the communication concerns.")
    ] = None
    sender: Annotated[
        Optional[str], Field(description="Who sent the communication.")
    ] = None
    recipient: Annotated[
        Optional[str], Field(description="Who received the communication.")
    ] = None

    @model_validator(mode="before")
    def _populate_type_from_comm_type(cls, values: dict):
        ct = values.get("communicationType")
        if (not values.get("type")) and isinstance(ct, dict):
            values["type"] = ct.get("name") or ct.get("code")
        return values


class Nomination(EntityBase):
    """Nomination record with nominee, position, and status information."""

    congress: Annotated[
        int, Field(description="Which Congress the nomination belongs to.")
    ]
    nominee: Annotated[str, Field(description="Who the nominee is.")]
    position: Annotated[str, Field(description="Which position the nominee is for.")]
    date: Annotated[
        Optional[datetime],
        Field(description="When the nomination was submitted or received."),
    ] = None
    status: Annotated[
        Optional[str],
        Field(description="What the current status of the nomination is."),
    ] = None
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the nomination record in the API."),
    ] = None
    committees: Annotated[
        Optional[List[str]],
        Field(description="Which committees are associated with the nomination."),
    ] = None
    subjects: Annotated[
        Optional[List[Subject]],
        Field(description="What subjects are tagged to the nomination."),
    ] = None


class CRSReport(EntityBase):
    """Congressional Research Service report metadata and summary."""

    title: Annotated[str, Field(description="What the CRS report title is.")]
    publish_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="publishDate",
            description="When the CRS report was published.",
        ),
    ] = None
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the CRS report in the API."),
    ] = None
    status: Annotated[
        Optional[str],
        Field(description="What the current status of the CRS report is."),
    ] = None
    summary: Annotated[
        Optional[str], Field(description="What summary text the report provides.")
    ] = None
    authors: Annotated[
        Optional[List[str]], Field(description="Who authored the CRS report.")
    ] = None
    topics: Annotated[
        Optional[List[Topic]], Field(description="Which topics the CRS report covers.")
    ] = None

    @model_validator(mode="before")
    def _normalize_input(cls, values: dict):
        # Normalize URL values missing a scheme
        url = values.get("url")
        if isinstance(url, str) and url.startswith("www."):
            values["url"] = f"https://{url}"

        # Normalize authors list entries which may be dicts like {"author": "Name"}
        authors = values.get("authors")
        if isinstance(authors, list):
            normalized = []
            for a in authors:
                if isinstance(a, dict) and "author" in a:
                    normalized.append(a.get("author"))
                elif isinstance(a, str):
                    normalized.append(a)
            values["authors"] = normalized

        # Copy publishDate (camelCase) into our snake_case `publish_date` field
        if values.get("publishDate") and not values.get("publish_date"):
            values["publish_date"] = values.get("publishDate")

        return values


class CommunicationTypeInfo(BaseModel):
    """Communication type code and display name."""

    code: Annotated[str, Field(description="What the communication type code is.")]
    name: Annotated[str, Field(description="What the communication type name is.")]


class VotePartyTotal(BaseModel):
    """Totals for a vote broken down by party or overall counts."""

    yea: Annotated[
        Optional[int],
        Field(default=None, description="Number of yea votes.", alias="yea"),
    ] = None
    nay: Annotated[
        Optional[int],
        Field(default=None, description="Number of nay votes.", alias="nay"),
    ] = None
    present: Annotated[
        Optional[int],
        Field(default=None, description="Number of present votes.", alias="present"),
    ] = None
    not_voting: Annotated[
        Optional[int],
        Field(default=None, description="Number of not voting.", alias="notVoting"),
    ] = None


class VoteQuestion(BaseModel):
    """Structured information about the question being voted on."""

    question: Annotated[
        Optional[str],
        Field(
            default=None, description="Human-readable question text.", alias="question"
        ),
    ] = None
    result: Annotated[
        Optional[str],
        Field(default=None, description="Result for this question.", alias="result"),
    ] = None
    required: Annotated[
        Optional[str],
        Field(
            default=None,
            description="What threshold was required for passage (e.g., 'majority').",
            alias="required",
        ),
    ] = None


class VoteCandidateTotal(BaseModel):
    """Per-candidate totals present in some vote payloads (e.g. Speaker election)."""

    candidate: Annotated[
        Optional[str],
        Field(default=None, description="Candidate name.", alias="candidate"),
    ] = None
    total: Annotated[
        Optional[int],
        Field(default=None, description="Total votes for candidate.", alias="total"),
    ] = None


class Section(BaseModel):
    """Section entry within a bound congressional record issue."""

    start_page: Annotated[
        Optional[int],
        Field(
            default=None,
            alias="startPage",
            description="Starting page for the section.",
        ),
    ] = None
    end_page: Annotated[
        Optional[int],
        Field(
            default=None, alias="endPage", description="Ending page for the section."
        ),
    ] = None
    title: Annotated[
        Optional[str],
        Field(default=None, alias="title", description="Section title if provided."),
    ] = None
    ordinal: Annotated[
        Optional[int],
        Field(
            default=None,
            alias="ordinal",
            description="Optional display order for the section.",
        ),
    ] = None

    model_config = {"populate_by_name": True}


# Type alias for sections container
Sections = list[Section]


class EntireIssueEntry(BaseModel):
    """Entry in `fullIssue.entireIssue` (e.g. PDF or formatted text part)."""

    part: Annotated[
        Optional[int],
        Field(default=None, alias="part", description="Part id when present"),
    ] = None
    type: Annotated[
        Optional[str], Field(default=None, alias="type", description="Format type")
    ] = None
    url: Annotated[
        Optional[HttpUrl],
        Field(default=None, alias="url", description="Where to fetch this part"),
    ] = None

    @model_validator(mode="before")
    def _coerce_part_to_int(cls, values: dict):
        p = values.get("part")
        if p is not None and not isinstance(p, int):
            try:
                if isinstance(p, str) and p.isdigit():
                    values["part"] = int(p)
                else:
                    values["part"] = int(str(p))
            except Exception:
                # leave as-is if coercion fails
                logger.exception("Failed to coerce entireIssue.part to int")
        return values


class DailySection(BaseModel):
    """Section entry used in `fullIssue.sections` for daily congressional record."""

    start_page: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="startPage",
            description="Starting page token (may include letter prefix, e.g. 'D299').",
        ),
    ] = None
    end_page: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="endPage",
            description="Ending page token (may include letter prefix).",
        ),
    ] = None
    name: Annotated[
        Optional[str], Field(default=None, alias="name", description="Section name")
    ] = None
    text: Annotated[
        Optional[List[Format]],
        Field(
            default=None,
            alias="text",
            description="List of formatted text or PDF entries for the section.",
        ),
    ] = None

    model_config = {"populate_by_name": True}


class FullIssue(BaseModel):
    """Container for the `fullIssue` payload returned by the API."""

    articles: Annotated[
        Optional[CountUrl],
        Field(default=None, alias="articles", description="Article count/url pair"),
    ] = None
    entire_issue: Annotated[
        Optional[List[EntireIssueEntry]],
        Field(
            default=None, alias="entireIssue", description="List of entireIssue parts"
        ),
    ] = None
    sections: Annotated[
        Optional[List[DailySection]],
        Field(
            default=None, alias="sections", description="Sections within the full issue"
        ),
    ] = None

    model_config = {"populate_by_name": True}


class MemberDepiction(BaseModel):
    """Member image metadata used in list responses."""

    attribution: Annotated[
        Optional[str], Field(description="Who to credit for the member image.")
    ] = None
    image_url: Annotated[
        Optional[HttpUrl],
        Field(
            default=None,
            alias="imageUrl",
            description="Where to fetch the member image.",
        ),
    ]


class MemberTermItem(BaseModel):
    """Single term entry used in member list responses."""

    chamber: Annotated[
        Optional[str], Field(description="Which chamber the term was served in.")
    ] = None
    start_year: Annotated[
        Optional[int],
        Field(
            default=None, alias="startYear", description="What year the term started."
        ),
    ]
    end_year: Annotated[
        Optional[int],
        Field(default=None, alias="endYear", description="What year the term ended."),
    ]


class MemberTerms(BaseModel):
    """Container for member term entries in list responses."""

    item: Annotated[
        Optional[List[MemberTermItem]],
        Field(description="Which terms are listed for the member."),
    ] = None


class HouseCommunicationListItem(EntityBase, RecordTypeBase):
    """List-level House communication entry."""

    recordType: Annotated[
        str, Field(description="Which knowledgebase index this record belongs to.")
    ] = "congress-house-communications"

    chamber: Annotated[str, Field(description="Which chamber sent the communication.")]
    number: Annotated[int, Field(description="What the communication number is.")]
    communication_type: Annotated[
        Optional[CommunicationTypeInfo],
        Field(
            default=None,
            alias="communicationType",
            description="What communication type this is.",
        ),
    ]
    congress: Annotated[
        Optional[int], Field(description="Which Congress the communication belongs to.")
    ] = None
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the communication record in the API."),
    ] = None
    update_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="updateDate",
            description="When the communication was last updated.",
        ),
    ]


class SenateCommunicationListItem(EntityBase, RecordTypeBase):
    """List-level Senate communication entry."""

    recordType: Annotated[
        str, Field(description="Which knowledgebase index this record belongs to.")
    ] = "congress-senate-communications"

    chamber: Annotated[str, Field(description="Which chamber sent the communication.")]
    number: Annotated[int, Field(description="What the communication number is.")]
    communication_type: Annotated[
        Optional[CommunicationTypeInfo],
        Field(
            default=None,
            alias="communicationType",
            description="What communication type this is.",
        ),
    ]
    congress: Annotated[
        Optional[int], Field(description="Which Congress the communication belongs to.")
    ] = None
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the communication record in the API."),
    ] = None
    update_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="updateDate",
            description="When the communication was last updated.",
        ),
    ]


class HouseRequirementListItem(EntityBase, RecordTypeBase):
    """List-level House requirement entry."""

    recordType: Annotated[
        str, Field(description="Which knowledgebase index this record belongs to.")
    ] = "congress-house-requirements"

    number: Annotated[int, Field(description="What the requirement number is.")]
    update_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="updateDate",
            description="When the requirement was last updated.",
        ),
    ]
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the requirement record in the API."),
    ] = None


class NominationLatestAction(BaseModel):
    """Latest action metadata attached to a nomination list item."""

    action_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="actionDate",
            description="When the latest action occurred.",
        ),
    ]
    text: Annotated[
        Optional[str], Field(description="What the latest action text says.")
    ] = None


class NominationTypeInfo(BaseModel):
    """Nomination type flags indicating military or civilian status."""

    is_military: Annotated[
        Optional[bool],
        Field(
            default=None,
            alias="isMilitary",
            description="Whether the nomination is military.",
        ),
    ]
    is_civilian: Annotated[
        Optional[bool],
        Field(
            default=None,
            alias="isCivilian",
            description="Whether the nomination is civilian.",
        ),
    ]


class NominationListItem(EntityBase, RecordTypeBase):
    """List-level nomination entry with citation and action data."""

    recordType: Annotated[
        str, Field(description="Which knowledgebase index this record belongs to.")
    ] = "congress-nominations"

    congress: Annotated[
        int, Field(description="Which Congress the nomination belongs to.")
    ]
    number: Annotated[int, Field(description="What the nomination number is.")]
    part_number: Annotated[
        Optional[int | str],
        Field(
            default=None,
            alias="partNumber",
            description="What part number the nomination has.",
        ),
    ]
    citation: Annotated[
        Optional[str], Field(description="What the official nomination citation is.")
    ] = None
    description: Annotated[
        Optional[str], Field(description="What the nomination describes.")
    ] = None
    received_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="receivedDate",
            description="When the nomination was received.",
        ),
    ]
    latest_action: Annotated[
        Optional[NominationLatestAction],
        Field(
            default=None, alias="latestAction", description="What the latest action is."
        ),
    ]
    nomination_type: Annotated[
        Optional[NominationTypeInfo],
        Field(
            default=None,
            alias="nominationType",
            description="What type of nomination this is.",
        ),
    ]
    update_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="updateDate",
            description="When the nomination was last updated.",
        ),
    ]
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the nomination record in the API."),
    ] = None
    organization: Annotated[
        Optional[str], Field(description="Which organization the nomination is for.")
    ] = None


class CRSReportListItem(EntityBase, RecordTypeBase):
    """List-level CRS report entry with status and metadata."""

    recordType: Annotated[
        str, Field(description="Which knowledgebase index this record belongs to.")
    ] = "congress-crs-reports"

    status: Annotated[
        Optional[str], Field(description="What the CRS report status is.")
    ] = None
    # canonical id provided by EntityBase heuristics
    publish_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="publishDate",
            description="When the report was published.",
        ),
    ]
    version: Annotated[
        Optional[int | str], Field(description="Which version of the report this is.")
    ] = None
    content_type: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="contentType",
            description="What content type the report is.",
        ),
    ]
    update_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="updateDate",
            description="When the report was last updated.",
        ),
    ]
    title: Annotated[Optional[str], Field(description="What the report title is.")] = (
        None
    )
    url: Annotated[
        Optional[HttpUrl], Field(description="Where to retrieve the report in the API.")
    ] = None


class BillSummaryBill(BaseModel):
    """Bill reference embedded in a summary list item."""

    congress: Annotated[int, Field(description="Which Congress the bill belongs to.")]
    type: Annotated[str, Field(description="What type of bill this is.")]
    origin_chamber: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="originChamber",
            description="Which chamber introduced the bill.",
        ),
    ]
    origin_chamber_code: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="originChamberCode",
            description="What the origin chamber code is.",
        ),
    ]
    number: Annotated[int, Field(description="What the bill number is.")]
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the bill record in the API."),
    ] = None
    title: Annotated[Optional[str], Field(description="What the bill title is.")] = None
    update_date_including_text: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="updateDateIncludingText",
            description="When the bill or its text was last updated.",
        ),
    ]


class BillSummaryListItem(EntityBase, RecordTypeBase):
    """List-level bill summary entry with action and version details."""

    recordType: Annotated[
        str, Field(description="Which knowledgebase index this record belongs to.")
    ] = "congress-summaries"

    bill: Annotated[
        BillSummaryBill, Field(description="Which bill the summary applies to.")
    ]
    text: Annotated[Optional[str], Field(description="What the summary text says.")] = (
        None
    )
    action_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="actionDate",
            description="When the summary action occurred.",
        ),
    ]
    update_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="updateDate",
            description="When the summary was last updated.",
        ),
    ]
    current_chamber: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="currentChamber",
            description="Which chamber the summary references.",
        ),
    ]
    current_chamber_code: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="currentChamberCode",
            description="What the chamber code is for the summary.",
        ),
    ]
    action_desc: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="actionDesc",
            description="What the summary action describes.",
        ),
    ]
    version_code: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="versionCode",
            description="Which version of the summary this is.",
        ),
    ]
    last_summary_update_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="lastSummaryUpdateDate",
            description="When the summary was last updated at the source.",
        ),
    ]


class HouseRollCallVoteListItem(EntityBase, RecordTypeBase):
    """List-level roll call vote entry for the House."""

    recordType: Annotated[
        str, Field(description="Which knowledgebase index this record belongs to.")
    ] = "congress-house-votes"

    start_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="startDate", description="When the vote started."),
    ]
    update_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="updateDate",
            description="When the vote record was last updated.",
        ),
    ]
    identifier: Annotated[
        Optional[int | str], Field(description="What the roll call vote identifier is.")
    ] = None
    congress: Annotated[
        Optional[int], Field(description="Which Congress the vote belongs to.")
    ] = None
    session_number: Annotated[
        Optional[int],
        Field(
            default=None,
            alias="sessionNumber",
            description="Which session the vote occurred in.",
        ),
    ]
    roll_call_number: Annotated[
        Optional[int],
        Field(
            default=None,
            alias="rollCallNumber",
            description="What the roll call number is.",
        ),
    ]
    vote_type: Annotated[
        Optional[str],
        Field(
            default=None, alias="voteType", description="What type of vote this was."
        ),
    ]
    result: Annotated[Optional[str], Field(description="What the vote result was.")] = (
        None
    )
    legislation_type: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="legislationType",
            description="What type of legislation the vote was on.",
        ),
    ]
    legislation_number: Annotated[
        Optional[int],
        Field(
            default=None,
            alias="legislationNumber",
            description="What the legislation number was.",
        ),
    ]
    amendment_type: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="amendmentType",
            description="What type of amendment was voted on.",
        ),
    ]
    amendment_number: Annotated[
        Optional[int],
        Field(
            default=None,
            alias="amendmentNumber",
            description="What the amendment number was.",
        ),
    ]
    amendment_author: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="amendmentAuthor",
            description="Who authored the amendment.",
        ),
    ]
    vote_party_total: Annotated[
        Optional[VotePartyTotal],
        Field(
            default=None,
            alias="votePartyTotal",
            description="Totals for the vote broken down by party or category.",
        ),
    ] = None
    vote_question: Annotated[
        Optional[VoteQuestion],
        Field(
            default=None,
            alias="voteQuestion",
            description="Structured details about the question being voted on.",
        ),
    ] = None
    vote_candidate_total: Annotated[
        Optional[list[VoteCandidateTotal]],
        Field(
            default=None,
            alias="voteCandidateTotal",
            description="Per-candidate totals when present (preserved).",
        ),
    ] = None
    source_data_url: Annotated[
        Optional[HttpUrl],
        Field(
            default=None,
            alias="sourceDataURL",
            description="Where to retrieve the source vote data.",
        ),
    ]
    # Accept `legislationUrl` from the API as an alias for `url` while still
    # allowing `url` to be used when populating by name.
    url: Annotated[
        Optional[HttpUrl],
        Field(
            default=None,
            alias="legislationUrl",
            description="Where to retrieve the vote record in the API.",
        ),
    ] = None

    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    def _normalize_vote_fields(cls, values: dict):
        # operate only on dict-like inputs
        if not isinstance(values, dict):
            return values

        # Normalize voteQuestion string -> dict
        vq = values.get("voteQuestion") or values.get("vote_question")
        if isinstance(vq, str):
            norm_vq = {"question": vq}
            values["voteQuestion"] = norm_vq
            values["vote_question"] = norm_vq

        # Detect candidate-style votePartyTotal lists and preserve them
        vpt = values.get("votePartyTotal")
        if isinstance(vpt, list):
            is_candidate_style = any(
                isinstance(x, dict) and ("candidate" in x or "total" in x) for x in vpt
            )
            if is_candidate_style:
                values["voteCandidateTotal"] = vpt
                values.pop("votePartyTotal", None)
                logger.debug(
                    "Detected candidate-style votePartyTotal; moved to voteCandidateTotal"
                )
            else:
                # Attempt to aggregate list entries into standard totals
                totals = {"yea": 0, "nay": 0, "present": 0, "notVoting": 0}
                any_found = False
                for item in vpt:
                    if not isinstance(item, dict):
                        continue
                    for src, key in (
                        ("yeaTotal", "yea"),
                        ("yea", "yea"),
                        ("nayTotal", "nay"),
                        ("nay", "nay"),
                        ("presentTotal", "present"),
                        ("present", "present"),
                        ("notVotingTotal", "notVoting"),
                        ("notVoting", "notVoting"),
                        ("not_voting", "notVoting"),
                    ):
                        val = item.get(src)
                        if val is not None:
                            try:
                                totals[key] += int(val)
                                any_found = True
                            except Exception:
                                logger.exception(
                                    "Failed to parse vote party total value: %s", val
                                )
                if any_found:
                    values["votePartyTotal"] = totals

        # Map legislationUrl -> url so `url` is populated when legislationUrl present
        if values.get("legislationUrl") and not values.get("url"):
            values["url"] = values.get("legislationUrl")
        if "legislationUrl" in values:
            values.pop("legislationUrl", None)

        # Ensure vote_question (snake_case) is a structured dict when present
        if values.get("voteQuestion") and not values.get("vote_question"):
            vq2 = values.get("voteQuestion")
            if isinstance(vq2, str):
                values["vote_question"] = {"question": vq2}
            elif isinstance(vq2, dict):
                values["vote_question"] = vq2

        # Synthesize a deterministic `id` if missing using congress/session/roll_call
        if not values.get("id"):
            congress = values.get("congress")
            sess = values.get("sessionNumber") or values.get("session_number")
            roll = values.get("rollCallNumber") or values.get("roll_call_number")
            ident = values.get("identifier")
            if congress is not None and sess is not None and roll is not None:
                try:
                    values["id"] = (
                        f"house-rollcall-vote:{int(congress)}:{int(sess)}:{int(roll)}"
                    )
                except Exception:
                    values["id"] = f"house-rollcall-vote:{congress}:{sess}:{roll}"
            elif ident is not None:
                values["id"] = f"house-rollcall-vote:{ident}"

        return values


class DailyCongressionalRecordIssue(EntityBase, RecordTypeBase):
    """List-level daily congressional record issue entry."""

    recordType: Annotated[
        str, Field(description="Which knowledgebase index this record belongs to.")
    ] = "congress-daily-congressional-records"

    congress: Annotated[
        Optional[int], Field(description="Which Congress the record issue belongs to.")
    ] = None
    issue_date: Annotated[
        Optional[datetime],
        Field(
            default=None, alias="issueDate", description="When the issue was published."
        ),
    ]
    issue_number: Annotated[
        Optional[int | str],
        Field(
            default=None, alias="issueNumber", description="What the issue number is."
        ),
    ]
    session_number: Annotated[
        Optional[int | str],
        Field(
            default=None,
            alias="sessionNumber",
            description="Which session the issue belongs to.",
        ),
    ]
    update_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="updateDate",
            description="When the issue was last updated.",
        ),
    ]
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the issue record in the API."),
    ] = None
    full_issue: Annotated[
        Optional[FullIssue],
        Field(
            default=None,
            alias="fullIssue",
            description="Expanded fullIssue payload including sections and entireIssue parts.",
        ),
    ] = None
    volume_number: Annotated[
        Optional[int | str],
        Field(
            default=None, alias="volumeNumber", description="What the volume number is."
        ),
    ]
    # Preserve the original API envelope when available
    issue: Annotated[
        Optional[dict],
        Field(
            default=None,
            alias="issue",
            description="Original API issue envelope (preserved for forensics).",
        ),
    ] = None

    def build_id(self) -> str:
        """Build deterministic id from `volume_number` + `issue_number` when possible.

        Format: daily-congressional-record:<volumeNumber>:<issueNumber>
        """
        # prefer existing id when available
        if getattr(self, "id", None):
            return str(self.id)

        try:
            vol = getattr(self, "volume_number", None) or getattr(
                self, "volumeNumber", None
            )
            issue = getattr(self, "issue_number", None) or getattr(
                self, "issueNumber", None
            )
            if vol is not None and issue is not None:
                try:
                    return f"daily-congressional-record:{int(vol)}:{int(issue)}"
                except Exception as exc:
                    logger.exception(
                        "Failed to coerce volume/issue to int for id build: %s/%s",
                        exc,
                    )
                    return f"daily-congressional-record:{vol}:{issue}"
        except Exception as exc:
            logger.exception(
                "Unexpected error while building daily congressional record id: %s", exc
            )

        # fallback to canonical behavior
        return super().build_id()


class BoundCongressionalRecordListItem(EntityBase, RecordTypeBase):
    """List-level bound congressional record entry."""

    recordType: Annotated[
        str, Field(description="Which knowledgebase index this record belongs to.")
    ] = "congress-bound-congressional-records"

    date: Annotated[
        Optional[datetime], Field(description="When the bound record was published.")
    ] = None
    volume_number: Annotated[
        Optional[int | str],
        Field(
            default=None, alias="volumeNumber", description="What the volume number is."
        ),
    ]
    congress: Annotated[
        Optional[int | str],
        Field(description="Which Congress the bound record belongs to."),
    ] = None
    session_number: Annotated[
        Optional[int | str],
        Field(
            default=None,
            alias="sessionNumber",
            description="Which session the record belongs to.",
        ),
    ]
    update_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="updateDate",
            description="When the bound record was last updated.",
        ),
    ]
    sections: Annotated[
        Optional[Sections],
        Field(default=None, alias="sections", description="Sections within the issue."),
    ] = None
    daily_digest: Annotated[
        Optional[dict],
        Field(
            default=None, alias="dailyDigest", description="Daily Digest information."
        ),
    ] = None
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the bound record in the API."),
    ] = None
    reference_id: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="referenceId",
            description="Reference id parsed from the source URL (non-unique).",
        ),
    ] = None

    @model_validator(mode="before")
    def _normalize_bound_record_fields(cls, values: dict):
        # Normalize dailyDigest which may be returned in multiple shapes
        dd = values.get("dailyDigest")
        if dd is not None and not isinstance(dd, dict):
            # Accept list or string shapes and coerce to a dict for the model
            try:
                if isinstance(dd, list) and dd:
                    first = dd[0]
                    if isinstance(first, dict):
                        values["dailyDigest"] = first
                    else:
                        values["dailyDigest"] = {"value": first}
                elif isinstance(dd, str):
                    values["dailyDigest"] = {"summary": dd}
                else:
                    # fallback: coerce to string representation
                    values["dailyDigest"] = {"value": str(dd)}
            except Exception:
                values["dailyDigest"] = None

        # If dailyDigest is now a dict, normalize any camelCase page keys inside it
        if isinstance(values.get("dailyDigest"), dict):
            ddn = values.get("dailyDigest")
            if ddn.get("startPage") and not ddn.get("start_page"):
                ddn["start_page"] = ddn.get("startPage")
            if ddn.get("endPage") and not ddn.get("end_page"):
                ddn["end_page"] = ddn.get("endPage")
            if "startPage" in ddn:
                ddn.pop("startPage", None)
            if "endPage" in ddn:
                ddn.pop("endPage", None)
            values["dailyDigest"] = ddn

        # Preserve snake_case aliases and remove camelCase originals to avoid duplicates
        if values.get("recordType") and not values.get("record_type"):
            values["record_type"] = values.get("recordType")
        if "recordType" in values:
            values.pop("recordType", None)

        # Map page fields
        if values.get("startPage") and not values.get("start_page"):
            values["start_page"] = values.get("startPage")
        if values.get("endPage") and not values.get("end_page"):
            values["end_page"] = values.get("endPage")
        # remove original camelCase page keys
        if "startPage" in values:
            values.pop("startPage", None)
        if "endPage" in values:
            values.pop("endPage", None)

        # Normalize any sections entries to snake_case page keys
        secs = values.get("sections")
        if isinstance(secs, list):
            normalized_secs = []
            for s in secs:
                if isinstance(s, dict):
                    if s.get("startPage") and not s.get("start_page"):
                        s["start_page"] = s.get("startPage")
                    if s.get("endPage") and not s.get("end_page"):
                        s["end_page"] = s.get("endPage")
                    # remove camelCase keys
                    if "startPage" in s:
                        s.pop("startPage", None)
                    if "endPage" in s:
                        s.pop("endPage", None)
                normalized_secs.append(s)
            values["sections"] = normalized_secs

        # Deduplicate referenceId -> reference_id and remove the camelCase key
        if values.get("referenceId") and not values.get("reference_id"):
            values["reference_id"] = values.get("referenceId")
        if "referenceId" in values:
            values.pop("referenceId", None)

        # Also preserve pagination/request envelopes into snake_case aliases if present
        if values.get("pagination") is None and values.get("pagination") is None:
            # nothing to do; keep whatever the wrapper parsing provides
            pass

        # Ensure daily_digest snake_case field populated from normalized dailyDigest
        if values.get("dailyDigest") and not values.get("daily_digest"):
            values["daily_digest"] = values.get("dailyDigest")
        # drop the camelCase wrapper now that we've copied into snake_case
        if "dailyDigest" in values:
            values.pop("dailyDigest", None)

        return values

    @model_validator(mode="before")
    def _populate_url_from_date(cls, values: dict):
        # Preserve existing URL when present; otherwise synthesize one
        # from the `date` field when available. ID generation is handled
        # by `build_id()` so canonical id logic remains centralized.
        if values.get("url"):
            return values

        dt = values.get("date")
        year = month = day = None
        try:
            if isinstance(dt, str) and dt:
                date_part = dt.split("T")[0]
                parts = date_part.split("-")
                if len(parts) >= 3:
                    year, month, day = (
                        parts[0],
                        parts[1].lstrip("0"),
                        parts[2].lstrip("0"),
                    )
            elif hasattr(dt, "year"):
                year = str(dt.year)
                month = str(dt.month)
                day = str(dt.day)
        except Exception as exc:
            logger.exception("Failed to parse date for URL synthesis: %s", exc)
            year = month = day = None

        if year and month and day:
            try:
                values["url"] = (
                    f"https://api.congress.gov/v3/bound-congressional-record/{year}/{int(month)}/{int(day)}?format=json"
                )
            except Exception as exc:
                logger.exception(
                    "Failed to build bound congressional record URL: %s", exc
                )

        return values

    @model_validator(mode="before")
    def _populate_reference_id_from_url(cls, values: dict):
        # populate `reference_id` from the url when possible so other records
        # can reference this item deterministically without requiring the
        # unique per-section `id`.
        if not values.get("reference_id") and values.get("url"):
            try:
                from src.data_collection.id_utils import parse_url_to_id

                values["reference_id"] = parse_url_to_id(str(values.get("url")))
            except Exception as exc:
                logger.exception("Failed to parse reference id from URL: %s", exc)
        return values

    def build_id(self) -> str:
        """Build a deterministic id from the `date` when `id` is missing.

        Format: bound-congressional-record:<year>:<month>:<day>
        """
        # prefer existing id when available
        if getattr(self, "id", None):
            return str(self.id)

        dt = getattr(self, "date", None)
        year = month = day = None
        try:
            if isinstance(dt, str) and dt:
                date_part = dt.split("T")[0]
                parts = date_part.split("-")
                if len(parts) >= 3:
                    year, month, day = parts[0], parts[1], parts[2]
            elif hasattr(dt, "year"):
                year = str(dt.year)
                month = str(dt.month)
                day = str(dt.day)
        except Exception:
            year = month = day = None

        if year and month and day:
            try:
                base = f"bound-congressional-record:{year}:{int(month)}:{int(day)}"
                # If this list item represents a specific section (or has
                # dailyDigest bounds), append startPage:endPage to produce
                # a unique id per-section. Prefer the first `sections`
                # entry when present, otherwise fall back to `daily_digest`.
                sp = ep = None
                try:
                    secs = getattr(self, "sections", None) or []
                    if isinstance(secs, list) and len(secs) > 0:
                        first = secs[0]
                        if isinstance(first, dict):
                            sp = first.get("start_page") or first.get("startPage")
                            ep = first.get("end_page") or first.get("endPage")
                        else:
                            # Pydantic `Section` instances or similar
                            sp = getattr(first, "start_page", None) or getattr(
                                first, "startPage", None
                            )
                            ep = getattr(first, "end_page", None) or getattr(
                                first, "endPage", None
                            )
                except Exception:
                    sp = ep = None

                if (sp is None or ep is None) and getattr(self, "daily_digest", None):
                    try:
                        dd = getattr(self, "daily_digest")
                        if isinstance(dd, dict):
                            sp = dd.get("start_page") or dd.get("startPage")
                            ep = dd.get("end_page") or dd.get("endPage")
                    except Exception:
                        sp = ep = None

                if sp is not None and ep is not None:
                    try:
                        return f"{base}:{int(sp)}:{int(ep)}"
                    except Exception:
                        # if conversion fails, fall back to base
                        return base

                return base
            except Exception as exc:
                logger.exception(
                    "Unexpected error while building bound congressional record id: %s",
                    exc,
                )

        # fallback to superclass logic (may raise ValueError)
        return super().build_id()


class CongressionalRecordIssue(EntityBase, RecordTypeBase):
    """Issue metadata from the Congressional Record feed."""

    recordType: Annotated[
        str, Field(description="Which knowledgebase index this record belongs to.")
    ] = "congress-congressional-records"

    congress: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="Congress",
            description="Which Congress the issue belongs to.",
        ),
    ]
    source_id: Annotated[
        Optional[int],
        Field(default=None, alias="Id", description="What the issue identifier is."),
    ]
    issue: Annotated[
        Optional[str],
        Field(default=None, alias="Issue", description="What the issue number is."),
    ]
    links: Annotated[
        Optional[dict[str, object]],
        Field(
            default=None,
            alias="Links",
            description="What related links are provided for the issue.",
        ),
    ]
    publish_date: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="PublishDate",
            description="When the issue was published.",
        ),
    ]
    session: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="Session",
            description="Which session the issue belongs to.",
        ),
    ]
    volume: Annotated[
        Optional[str],
        Field(default=None, alias="Volume", description="What the volume number is."),
    ]


class CommitteeListItem(EntityBase, RecordTypeBase):
    """List-level committee entry with system code and metadata."""

    recordType: Annotated[
        str, Field(description="Which knowledgebase index this record belongs to.")
    ] = "congress-committees"

    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the committee in the API."),
    ] = None
    system_code: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="systemCode",
            description="What the committee system code is.",
        ),
    ]
    name: Annotated[Optional[str], Field(description="What the committee name is.")] = (
        None
    )
    chamber: Annotated[
        Optional[str], Field(description="Which chamber the committee belongs to.")
    ] = None
    committee_type_code: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="committeeTypeCode",
            description="What the committee type code is.",
        ),
    ]
    update_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="updateDate",
            description="When the committee was last updated.",
        ),
    ]


class CommitteeReportListItem(EntityBase, RecordTypeBase):
    """List-level committee report entry with citation metadata."""

    recordType: Annotated[
        str, Field(description="Which knowledgebase index this record belongs to.")
    ] = "congress-committee-reports"

    citation: Annotated[
        Optional[str], Field(description="What the committee report citation is.")
    ] = None
    cmte_rpt_id: Annotated[
        Optional[int],
        Field(
            default=None,
            alias="cmte_rpt_id",
            description="What the committee report identifier is.",
        ),
    ]
    url: Annotated[
        Optional[HttpUrl], Field(description="Where to retrieve the report in the API.")
    ] = None
    update_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="updateDate",
            description="When the report was last updated.",
        ),
    ]
    congress: Annotated[
        Optional[int], Field(description="Which Congress the report belongs to.")
    ] = None
    chamber: Annotated[
        Optional[str], Field(description="Which chamber issued the report.")
    ] = None
    type: Annotated[
        Optional[str], Field(description="What type of committee report this is.")
    ] = None
    number: Annotated[
        Optional[int], Field(description="What the report number is.")
    ] = None
    part: Annotated[
        Optional[int], Field(description="Which part of a multi-part report this is.")
    ] = None


class AmendmentLatestAction(BaseModel):
    """Latest action metadata attached to an amendment list item."""

    action_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="actionDate",
            description="When the latest action occurred.",
        ),
    ]
    action_time: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="actionTime",
            description="What time the latest action occurred.",
        ),
    ]
    text: Annotated[
        Optional[str], Field(description="What the latest action text says.")
    ] = None


class AmendmentListItem(EntityBase, RecordTypeBase):
    """List-level amendment entry with latest action and type."""

    recordType: Annotated[
        str, Field(description="Which knowledgebase index this record belongs to.")
    ] = "congress-amendments"

    congress: Annotated[
        Optional[int], Field(description="Which Congress the amendment belongs to.")
    ] = None
    description: Annotated[
        Optional[str], Field(description="What the amendment description says.")
    ] = None
    latest_action: Annotated[
        Optional[AmendmentLatestAction],
        Field(
            default=None, alias="latestAction", description="What the latest action is."
        ),
    ]
    number: Annotated[
        Optional[str], Field(description="What the amendment number is.")
    ] = None
    purpose: Annotated[
        Optional[str], Field(description="What purpose the amendment states.")
    ] = None
    type: Annotated[
        Optional[str], Field(description="What type of amendment this is.")
    ] = None
    update_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="updateDate",
            description="When the amendment was last updated.",
        ),
    ]
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the amendment in the API."),
    ] = None


class BillLatestAction(BaseModel):
    """Latest action metadata attached to a bill list item."""

    action_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="actionDate",
            description="When the latest action occurred.",
        ),
    ]
    text: Annotated[
        Optional[str], Field(description="What the latest action text says.")
    ] = None


class LawEntry(BaseModel):
    """Law entry used in law list items (number and type)."""

    number: Annotated[Optional[str], Field(description="What the law number is.")] = (
        None
    )
    type: Annotated[
        Optional[str], Field(description="What type of law this is (public/private).")
    ] = None


class BillListItem(EntityBase, RecordTypeBase):
    """List-level bill entry with title and latest action."""

    recordType: Annotated[
        str, Field(description="Which knowledgebase index this record belongs to.")
    ] = "congress-bills"

    congress: Annotated[
        Optional[int], Field(description="Which Congress the bill belongs to.")
    ] = None
    latest_action: Annotated[
        Optional[BillLatestAction],
        Field(
            default=None, alias="latestAction", description="What the latest action is."
        ),
    ]
    number: Annotated[Optional[str], Field(description="What the bill number is.")] = (
        None
    )
    origin_chamber: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="originChamber",
            description="Which chamber introduced the bill.",
        ),
    ]
    origin_chamber_code: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="originChamberCode",
            description="What the origin chamber code is.",
        ),
    ]
    title: Annotated[Optional[str], Field(description="What the bill title is.")] = None
    type: Annotated[Optional[str], Field(description="What type of bill this is.")] = (
        None
    )
    update_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="updateDate",
            description="When the bill was last updated.",
        ),
    ]
    update_date_including_text: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="updateDateIncludingText",
            description="When the bill or its text was last updated.",
        ),
    ]
    url: Annotated[
        Optional[HttpUrl], Field(description="Where to retrieve the bill in the API.")
    ] = None


class LawListItem(EntityBase, RecordTypeBase):
    """List-level law entry derived from bill data."""

    recordType: Annotated[
        str, Field(description="Which knowledgebase index this record belongs to.")
    ] = "congress-laws"

    congress: Annotated[
        Optional[int], Field(description="Which Congress the law belongs to.")
    ] = None
    latest_action: Annotated[
        Optional[BillLatestAction],
        Field(
            default=None, alias="latestAction", description="What the latest action is."
        ),
    ]
    laws: Annotated[
        Optional[List[LawEntry]],
        Field(description="Which law entries are associated with the bill."),
    ] = None
    number: Annotated[Optional[str], Field(description="What the bill number is.")] = (
        None
    )
    origin_chamber: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="originChamber",
            description="Which chamber introduced the bill.",
        ),
    ]
    origin_chamber_code: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="originChamberCode",
            description="What the origin chamber code is.",
        ),
    ]
    title: Annotated[Optional[str], Field(description="What the bill title is.")] = None
    type: Annotated[Optional[str], Field(description="What type of bill this is.")] = (
        None
    )
    update_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="updateDate",
            description="When the law record was last updated.",
        ),
    ]
    update_date_including_text: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="updateDateIncludingText",
            description="When the law or its text was last updated.",
        ),
    ]
    url: Annotated[
        Optional[HttpUrl], Field(description="Where to retrieve the law in the API.")
    ] = None


class CommitteePrintListItem(EntityBase, RecordTypeBase):
    """List-level committee print entry."""

    recordType: Annotated[
        str, Field(description="Which knowledgebase index this record belongs to.")
    ] = "congress-committee-prints"

    jacket_number: Annotated[
        Optional[int],
        Field(
            default=None, alias="jacketNumber", description="What the jacket number is."
        ),
    ]
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the committee print in the API."),
    ] = None
    update_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="updateDate",
            description="When the committee print was last updated.",
        ),
    ]
    congress: Annotated[
        Optional[int],
        Field(description="Which Congress the committee print belongs to."),
    ] = None
    chamber: Annotated[
        Optional[str],
        Field(description="Which chamber the committee print belongs to."),
    ] = None


class CommitteeMeetingListItem(EntityBase, RecordTypeBase):
    """List-level committee meeting entry."""

    recordType: Annotated[
        str, Field(description="Which knowledgebase index this record belongs to.")
    ] = "congress-committee-meetings"

    event_id: Annotated[
        Optional[int],
        Field(
            default=None,
            alias="eventId",
            description="What the meeting event identifier is.",
        ),
    ]
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the meeting in the API."),
    ] = None
    update_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="updateDate",
            description="When the meeting was last updated.",
        ),
    ]
    congress: Annotated[
        Optional[int], Field(description="Which Congress the meeting belongs to.")
    ] = None
    chamber: Annotated[
        Optional[str], Field(description="Which chamber the meeting belongs to.")
    ] = None


class HearingListItem(EntityBase, RecordTypeBase):
    """List-level hearing entry with jacket number and metadata."""

    recordType: Annotated[
        str, Field(description="Which knowledgebase index this record belongs to.")
    ] = "congress-hearings"

    jacket_number: Annotated[
        Optional[int],
        Field(
            default=None,
            alias="jacketNumber",
            description="What the hearing jacket number is.",
        ),
    ]
    update_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="updateDate",
            description="When the hearing was last updated.",
        ),
    ]
    chamber: Annotated[
        Optional[str], Field(description="Which chamber held the hearing.")
    ] = None
    congress: Annotated[
        Optional[int], Field(description="Which Congress the hearing belongs to.")
    ] = None
    number: Annotated[
        Optional[int], Field(description="What the hearing number is.")
    ] = None
    part: Annotated[
        Optional[int], Field(description="Which part of a multipart hearing this is.")
    ] = None
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the hearing in the API."),
    ] = None


class TreatyListItem(EntityBase, RecordTypeBase):
    """List-level treaty entry with congress and numbering info."""

    recordType: Annotated[
        str, Field(description="Which knowledgebase index this record belongs to.")
    ] = "congress-treaties"

    congress_received: Annotated[
        Optional[int],
        Field(
            default=None,
            alias="congressReceived",
            description="Which Congress received the treaty.",
        ),
    ]
    congress_considered: Annotated[
        Optional[int],
        Field(
            default=None,
            alias="congressConsidered",
            description="Which Congress considered the treaty.",
        ),
    ]
    number: Annotated[
        Optional[int], Field(description="What the treaty number is.")
    ] = None
    parts: Annotated[
        Optional[dict[str, object]],
        Field(description="What parts the treaty is divided into."),
    ] = None
    suffix: Annotated[
        Optional[str], Field(description="What suffix the treaty carries.")
    ] = None
    topic: Annotated[
        Optional[str], Field(description="What topic the treaty concerns.")
    ] = None
    transmitted_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="transmittedDate",
            description="When the treaty was transmitted.",
        ),
    ]
    update_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="updateDate",
            description="When the treaty was last updated.",
        ),
    ]
    url: Annotated[
        Optional[HttpUrl], Field(description="Where to retrieve the treaty in the API.")
    ] = None


class MemberListItem(EntityBase, RecordTypeBase):
    """List-level member entry with name, party, and term data."""

    recordType: Annotated[
        str, Field(description="Which knowledgebase index this record belongs to.")
    ] = "congress-members"

    bioguide_id: Annotated[
        str,
        Field(
            alias="bioguideId", description="What the member's Bioguide identifier is."
        ),
    ]
    state: Annotated[
        Optional[str],
        Field(description="Which state or territory the member represents."),
    ] = None
    party_name: Annotated[
        Optional[str],
        Field(
            default=None,
            alias="partyName",
            description="What the member's party name is.",
        ),
    ]
    district: Annotated[
        Optional[int],
        Field(description="Which congressional district the member represents."),
    ] = None
    name: Annotated[
        Optional[str], Field(description="What the member's display name is.")
    ] = None
    depiction: Annotated[
        Optional[MemberDepiction],
        Field(description="What image information is available for the member."),
    ] = None
    terms: Annotated[
        Optional[MemberTerms],
        Field(description="Which terms are listed for the member."),
    ] = None
    update_date: Annotated[
        Optional[datetime],
        Field(
            default=None,
            alias="updateDate",
            description="When the member record was last updated.",
        ),
    ]
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the member record in the API."),
    ] = None


# --- Parameter Models for Endpoint URLs ---


class CommitteeCode(str):
    """Validation wrapper for committee system codes."""

    """
    Unique code for a committee or subcommittee. Accepts any string matching the convention:
    - 4 alphabetic characters (case-insensitive), followed by 2 numeric digits (e.g., 'hspw00', 'sscm14').
    See: https://www.congress.gov/help/committee-name-history
    """

    @classmethod
    def __get_validators__(cls):
        """Yield validators for pydantic integration."""
        yield cls.validate

    @classmethod
    def validate(cls, v):
        """Validate committee code format and normalize to lowercase."""
        import re

        if not isinstance(v, str):
            raise TypeError("CommitteeCode must be a string")
        if not re.fullmatch(r"[a-zA-Z]{4}\d{2}", v):
            raise ValueError(
                f"CommitteeCode '{v}' must match pattern: 4 alpha + 2 digits (e.g., 'hspw00')"
            )
        return v.lower()


class ReportType(StrEnum):
    """Enumeration of committee report types used in endpoints."""

    """
    Type of committee report.
    - HRPT: House Report
    - SRPT: Senate Report
    - ERPT: Executive Report (Treaty)
    """
    HRPT = "hrpt"
    SRPT = "srpt"
    ERPT = "erpt"


class CommunicationType(StrEnum):
    """Enumeration of communication types used in endpoints."""

    """
    Type of communication sent to a committee.
    - EC: Executive Communication
    - PM: Presidential Message
    - PT: Petition
    - ML: Memorial
    - POM: Petition or Memorial (Senate)
    """
    EC = "ec"
    PM = "pm"
    PT = "pt"
    ML = "ml"
    POM = "pom"


class EventId(BaseModel):
    """Wrapper for event identifiers used in hearings or meetings."""

    """
    Unique identifier for an event (e.g., hearing, meeting) in the Congressional Record or committee schedule.
    """
    event_id: Annotated[str, Field(description="What the event identifier is.")]


class JacketNumber(BaseModel):
    """Wrapper for jacket numbers assigned to hearings or reports."""

    """
    The jacket number assigned to a printed hearing or committee report.
    """
    jacket_number: Annotated[int, Field(description="What the jacket number is.")]


class VolumeNumber(BaseModel):
    """Wrapper for volume numbers of the Congressional Record."""

    """
    The volume number for Congressional Record or other serial publications.
    """
    volume_number: Annotated[int, Field(description="What the volume number is.")]


class IssueNumber(BaseModel):
    """Wrapper for issue numbers of the Congressional Record."""

    """
    The issue number for Congressional Record or other serial publications.
    """
    issue_number: Annotated[int, Field(description="What the issue number is.")]


class StateCode(StrEnum):
    """Enumeration of state and territory postal codes."""

    """
    Two-letter postal code abbreviation for U.S. states, territories, and districts.
    See: https://www.congress.gov/help/field-values/state-territory
    """
    AL = "AL"
    AK = "AK"
    AZ = "AZ"
    AR = "AR"
    CA = "CA"
    CO = "CO"
    CT = "CT"
    DE = "DE"
    FL = "FL"
    GA = "GA"
    HI = "HI"
    ID = "ID"
    IL = "IL"
    IN = "IN"
    IA = "IA"
    KS = "KS"
    KY = "KY"
    LA = "LA"
    ME = "ME"
    MD = "MD"
    MA = "MA"
    MI = "MI"
    MN = "MN"
    MS = "MS"
    MO = "MO"
    MT = "MT"
    NE = "NE"
    NV = "NV"
    NH = "NH"
    NJ = "NJ"
    NM = "NM"
    NY = "NY"
    NC = "NC"
    ND = "ND"
    OH = "OH"
    OK = "OK"
    OR = "OR"
    PA = "PA"
    RI = "RI"
    SC = "SC"
    SD = "SD"
    TN = "TN"
    TX = "TX"
    UT = "UT"
    VT = "VT"
    VA = "VA"
    WA = "WA"
    WV = "WV"
    WI = "WI"
    WY = "WY"


class District(BaseModel):
    """Wrapper for congressional district numbers."""

    """
    Congressional district number. Value is 0 for states/territories with only one district.
    """
    district: Annotated[int, Field(description="What the district number is.")]


class RequirementNumber(BaseModel):
    """Wrapper for House requirement identifiers."""

    """
    Unique identifier for a House requirement (e.g., for rules or reserved bills).
    """
    requirement_number: Annotated[
        int, Field(description="What the requirement number is.")
    ]


class Ordinal(BaseModel):
    """Wrapper for ordinal values used in ordered lists."""

    """
    Ordinal value used for display order (e.g., nominee positions, digest sections).
    """
    ordinal: Annotated[int, Field(description="What the ordinal position is.")]


class TreatySuffix(BaseModel):
    """Wrapper for treaty suffix designators."""

    """
    Suffix for partitioned treaties (e.g., 'A', 'B', 'C').
    """
    treaty_suffix: Annotated[str, Field(description="What the treaty suffix is.")]


class ReportNumber(BaseModel):
    """Wrapper for committee report numbers."""

    """
    The assigned committee report number.
    """
    report_number: Annotated[int, Field(description="What the report number is.")]


class BillNumber(BaseModel):
    """Wrapper for bill numbers in endpoint parameters."""

    """
    The assigned bill or resolution number.
    """
    bill_number: Annotated[int, Field(description="What the bill number is.")]


class LawNumber(BaseModel):
    """Wrapper for law numbers assigned by NARA."""

    """
    The law number, as assigned by NARA (e.g., 117-108).
    """
    law_number: Annotated[int, Field(description="What the law number is.")]


class AmendmentNumber(BaseModel):
    """Wrapper for amendment numbers in endpoint parameters."""

    """
    The assigned amendment number.
    """
    amendment_number: Annotated[int, Field(description="What the amendment number is.")]


class CommunicationNumber(BaseModel):
    """Wrapper for communication numbers in endpoint parameters."""

    """
    The assigned communication number for House or Senate communications.
    """
    communication_number: Annotated[
        int, Field(description="What the communication number is.")
    ]


class NominationNumber(BaseModel):
    """Wrapper for nomination numbers in endpoint parameters."""

    """
    The assigned nomination number (Presidential Nomination).
    """
    nomination_number: Annotated[
        int, Field(description="What the nomination number is.")
    ]


class TreatyNumber(BaseModel):
    """Wrapper for treaty numbers in endpoint parameters."""

    """
    The assigned treaty number.
    """
    treaty_number: Annotated[int, Field(description="What the treaty number is.")]


"""Additional Pydantic models for list items, auxiliary entities, and parameters.

Each model includes per-field descriptions that explain what each attribute answers.
"""

from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, HttpUrl, Field
from typing import Any, Annotated, List, Optional

# Subject class (structured, not just string)
class Subject(BaseModel):
    """Structured subject label with optional update timing."""
    name: Annotated[str, Field(description="What the subject name is.")]
    update_date: Annotated[
        Optional[datetime],
        Field(description="When the subject was last updated.")
    ] = None

# Topic class (structured, not just string)
class Topic(BaseModel):
    """Structured topic label with optional update timing."""
    topic: Annotated[str, Field(description="What the topic label is.")]
    update_date: Annotated[
        Optional[datetime],
        Field(description="When the topic was last updated.")
    ] = None

# House Communication model
class HouseCommunication(BaseModel):
    """House communication record with sender, recipient, and subject."""
    id: Annotated[str, Field(description="What the communication identifier is.")]
    type: Annotated[str, Field(description="What type of communication this is.")]
    date: Annotated[
        Optional[datetime],
        Field(description="When the communication was submitted.")
    ] = None
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the communication record in the API.")
    ] = None
    subject: Annotated[
        Optional[Subject],
        Field(description="What subject the communication concerns.")
    ] = None
    sender: Annotated[
        Optional[str],
        Field(description="Who sent the communication.")
    ] = None
    recipient: Annotated[
        Optional[str],
        Field(description="Who received the communication.")
    ] = None

# House Requirement model
class HouseRequirement(BaseModel):
    """House requirement record describing a required submission or report."""
    id: Annotated[str, Field(description="What the House requirement identifier is.")]
    type: Annotated[str, Field(description="What type of requirement this is.")]
    description: Annotated[
        Optional[str],
        Field(description="What the requirement describes.")
    ] = None
    date: Annotated[
        Optional[datetime],
        Field(description="When the requirement was recorded.")
    ] = None
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the requirement record in the API.")
    ] = None

# Senate Communication model
class SenateCommunication(BaseModel):
    """Senate communication record with sender, recipient, and subject."""
    id: Annotated[str, Field(description="What the communication identifier is.")]
    type: Annotated[str, Field(description="What type of communication this is.")]
    date: Annotated[
        Optional[datetime],
        Field(description="When the communication was submitted.")
    ] = None
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the communication record in the API.")
    ] = None
    subject: Annotated[
        Optional[Subject],
        Field(description="What subject the communication concerns.")
    ] = None
    sender: Annotated[
        Optional[str],
        Field(description="Who sent the communication.")
    ] = None
    recipient: Annotated[
        Optional[str],
        Field(description="Who received the communication.")
    ] = None

# Nomination model
class Nomination(BaseModel):
    """Nomination record with nominee, position, and status information."""
    id: Annotated[str, Field(description="What the nomination identifier is.")]
    congress: Annotated[int, Field(description="Which Congress the nomination belongs to.")]
    nominee: Annotated[str, Field(description="Who the nominee is.")]
    position: Annotated[str, Field(description="Which position the nominee is for.")]
    date: Annotated[
        Optional[datetime],
        Field(description="When the nomination was submitted or received.")
    ] = None
    status: Annotated[
        Optional[str],
        Field(description="What the current status of the nomination is.")
    ] = None
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the nomination record in the API.")
    ] = None
    committees: Annotated[
        Optional[List[str]],
        Field(description="Which committees are associated with the nomination.")
    ] = None
    subjects: Annotated[
        Optional[List[Subject]],
        Field(description="What subjects are tagged to the nomination.")
    ] = None

# CRS Report model
class CRSReport(BaseModel):
    """Congressional Research Service report metadata and summary."""
    id: Annotated[str, Field(description="What the CRS report identifier is.")]
    title: Annotated[str, Field(description="What the CRS report title is.")]
    publish_date: Annotated[
        Optional[datetime],
        Field(description="When the CRS report was published.")
    ] = None
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the CRS report in the API.")
    ] = None
    status: Annotated[
        Optional[str],
        Field(description="What the current status of the CRS report is.")
    ] = None
    summary: Annotated[
        Optional[str],
        Field(description="What summary text the report provides.")
    ] = None
    authors: Annotated[
        Optional[List[str]],
        Field(description="Who authored the CRS report.")
    ] = None
    topics: Annotated[
        Optional[List[Topic]],
        Field(description="Which topics the CRS report covers.")
    ] = None


class CommunicationTypeInfo(BaseModel):
    """Communication type code and display name."""
    code: Annotated[str, Field(description="What the communication type code is.")]
    name: Annotated[str, Field(description="What the communication type name is.")]


class MemberDepiction(BaseModel):
    """Member image metadata used in list responses."""
    attribution: Annotated[
        Optional[str],
        Field(description="Who to credit for the member image.")
    ] = None
    image_url: Annotated[
        Optional[HttpUrl],
        Field(default=None, alias="imageUrl", description="Where to fetch the member image.")
    ]


class MemberTermItem(BaseModel):
    """Single term entry used in member list responses."""
    chamber: Annotated[
        Optional[str],
        Field(description="Which chamber the term was served in.")
    ] = None
    start_year: Annotated[
        Optional[int],
        Field(default=None, alias="startYear", description="What year the term started.")
    ]
    end_year: Annotated[
        Optional[int],
        Field(default=None, alias="endYear", description="What year the term ended.")
    ]


class MemberTerms(BaseModel):
    """Container for member term entries in list responses."""
    item: Annotated[
        Optional[List[MemberTermItem]],
        Field(description="Which terms are listed for the member.")
    ] = None


class HouseCommunicationListItem(BaseModel):
    """List-level House communication entry."""
    chamber: Annotated[str, Field(description="Which chamber sent the communication.")]
    number: Annotated[int, Field(description="What the communication number is.")]
    communication_type: Annotated[
        Optional[CommunicationTypeInfo],
        Field(default=None, alias="communicationType", description="What communication type this is.")
    ]
    congress: Annotated[
        Optional[int],
        Field(description="Which Congress the communication belongs to.")
    ] = None
    congress_number: Annotated[
        Optional[int],
        Field(default=None, alias="congressNumber", description="Which Congress number is reported.")
    ]
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the communication record in the API.")
    ] = None
    update_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="updateDate", description="When the communication was last updated.")
    ]


class SenateCommunicationListItem(BaseModel):
    """List-level Senate communication entry."""
    chamber: Annotated[str, Field(description="Which chamber sent the communication.")]
    number: Annotated[int, Field(description="What the communication number is.")]
    communication_type: Annotated[
        Optional[CommunicationTypeInfo],
        Field(default=None, alias="communicationType", description="What communication type this is.")
    ]
    congress: Annotated[
        Optional[int],
        Field(description="Which Congress the communication belongs to.")
    ] = None
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the communication record in the API.")
    ] = None
    update_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="updateDate", description="When the communication was last updated.")
    ]


class HouseRequirementListItem(BaseModel):
    """List-level House requirement entry."""
    number: Annotated[int, Field(description="What the requirement number is.")]
    update_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="updateDate", description="When the requirement was last updated.")
    ]
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the requirement record in the API.")
    ] = None


class NominationLatestAction(BaseModel):
    """Latest action metadata attached to a nomination list item."""
    action_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="actionDate", description="When the latest action occurred.")
    ]
    text: Annotated[
        Optional[str],
        Field(description="What the latest action text says.")
    ] = None


class NominationTypeInfo(BaseModel):
    """Nomination type flags indicating military or civilian status."""
    is_military: Annotated[
        Optional[bool],
        Field(default=None, alias="isMilitary", description="Whether the nomination is military.")
    ]
    is_civilian: Annotated[
        Optional[bool],
        Field(default=None, alias="isCivilian", description="Whether the nomination is civilian.")
    ]


class NominationListItem(BaseModel):
    """List-level nomination entry with citation and action data."""
    congress: Annotated[int, Field(description="Which Congress the nomination belongs to.")]
    number: Annotated[int, Field(description="What the nomination number is.")]
    part_number: Annotated[
        Optional[int | str],
        Field(default=None, alias="partNumber", description="What part number the nomination has.")
    ]
    citation: Annotated[
        Optional[str],
        Field(description="What the official nomination citation is.")
    ] = None
    description: Annotated[
        Optional[str],
        Field(description="What the nomination describes.")
    ] = None
    received_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="receivedDate", description="When the nomination was received.")
    ]
    latest_action: Annotated[
        Optional[NominationLatestAction],
        Field(default=None, alias="latestAction", description="What the latest action is.")
    ]
    nomination_type: Annotated[
        Optional[NominationTypeInfo],
        Field(default=None, alias="nominationType", description="What type of nomination this is.")
    ]
    update_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="updateDate", description="When the nomination was last updated.")
    ]
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the nomination record in the API.")
    ] = None
    organization: Annotated[
        Optional[str],
        Field(description="Which organization the nomination is for.")
    ] = None


class CRSReportListItem(BaseModel):
    """List-level CRS report entry with status and metadata."""
    status: Annotated[
        Optional[str],
        Field(description="What the CRS report status is.")
    ] = None
    id: Annotated[str, Field(description="What the CRS report identifier is.")]
    publish_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="publishDate", description="When the report was published.")
    ]
    version: Annotated[
        Optional[int | str],
        Field(description="Which version of the report this is.")
    ] = None
    content_type: Annotated[
        Optional[str],
        Field(default=None, alias="contentType", description="What content type the report is.")
    ]
    update_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="updateDate", description="When the report was last updated.")
    ]
    title: Annotated[
        Optional[str],
        Field(description="What the report title is.")
    ] = None
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the report in the API.")
    ] = None


class BillSummaryBill(BaseModel):
    """Bill reference embedded in a summary list item."""
    congress: Annotated[int, Field(description="Which Congress the bill belongs to.")]
    type: Annotated[str, Field(description="What type of bill this is.")]
    origin_chamber: Annotated[
        Optional[str],
        Field(default=None, alias="originChamber", description="Which chamber introduced the bill.")
    ]
    origin_chamber_code: Annotated[
        Optional[str],
        Field(default=None, alias="originChamberCode", description="What the origin chamber code is.")
    ]
    number: Annotated[int, Field(description="What the bill number is.")]
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the bill record in the API.")
    ] = None
    title: Annotated[
        Optional[str],
        Field(description="What the bill title is.")
    ] = None
    update_date_including_text: Annotated[
        Optional[datetime],
        Field(default=None, alias="updateDateIncludingText", description="When the bill or its text was last updated.")
    ]


class BillSummaryListItem(BaseModel):
    """List-level bill summary entry with action and version details."""
    bill: Annotated[BillSummaryBill, Field(description="Which bill the summary applies to.")]
    text: Annotated[
        Optional[str],
        Field(description="What the summary text says.")
    ] = None
    action_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="actionDate", description="When the summary action occurred.")
    ]
    update_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="updateDate", description="When the summary was last updated.")
    ]
    current_chamber: Annotated[
        Optional[str],
        Field(default=None, alias="currentChamber", description="Which chamber the summary references.")
    ]
    current_chamber_code: Annotated[
        Optional[str],
        Field(default=None, alias="currentChamberCode", description="What the chamber code is for the summary.")
    ]
    action_desc: Annotated[
        Optional[str],
        Field(default=None, alias="actionDesc", description="What the summary action describes.")
    ]
    version_code: Annotated[
        Optional[str],
        Field(default=None, alias="versionCode", description="Which version of the summary this is.")
    ]
    last_summary_update_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="lastSummaryUpdateDate", description="When the summary was last updated at the source.")
    ]


class HouseRollCallVoteListItem(BaseModel):
    """List-level roll call vote entry for the House."""
    start_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="startDate", description="When the vote started.")
    ]
    update_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="updateDate", description="When the vote record was last updated.")
    ]
    identifier: Annotated[
        Optional[int | str],
        Field(description="What the roll call vote identifier is.")
    ] = None
    congress: Annotated[
        Optional[int],
        Field(description="Which Congress the vote belongs to.")
    ] = None
    session_number: Annotated[
        Optional[int],
        Field(default=None, alias="sessionNumber", description="Which session the vote occurred in.")
    ]
    roll_call_number: Annotated[
        Optional[int],
        Field(default=None, alias="rollCallNumber", description="What the roll call number is.")
    ]
    vote_type: Annotated[
        Optional[str],
        Field(default=None, alias="voteType", description="What type of vote this was.")
    ]
    result: Annotated[
        Optional[str],
        Field(description="What the vote result was.")
    ] = None
    legislation_type: Annotated[
        Optional[str],
        Field(default=None, alias="legislationType", description="What type of legislation the vote was on.")
    ]
    legislation_number: Annotated[
        Optional[int],
        Field(default=None, alias="legislationNumber", description="What the legislation number was.")
    ]
    amendment_type: Annotated[
        Optional[str],
        Field(default=None, alias="amendmentType", description="What type of amendment was voted on.")
    ]
    amendment_number: Annotated[
        Optional[int],
        Field(default=None, alias="amendmentNumber", description="What the amendment number was.")
    ]
    amendment_author: Annotated[
        Optional[str],
        Field(default=None, alias="amendmentAuthor", description="Who authored the amendment.")
    ]
    legislation_url: Annotated[
        Optional[HttpUrl],
        Field(default=None, alias="legislationUrl", description="Where to retrieve the legislation in the API.")
    ]
    source_data_url: Annotated[
        Optional[HttpUrl],
        Field(default=None, alias="sourceDataURL", description="Where to retrieve the source vote data.")
    ]
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the vote record in the API.")
    ] = None


class DailyCongressionalRecordIssue(BaseModel):
    """List-level daily congressional record issue entry."""
    congress: Annotated[
        Optional[int],
        Field(description="Which Congress the record issue belongs to.")
    ] = None
    issue_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="issueDate", description="When the issue was published.")
    ]
    issue_number: Annotated[
        Optional[int | str],
        Field(default=None, alias="issueNumber", description="What the issue number is.")
    ]
    session_number: Annotated[
        Optional[int | str],
        Field(default=None, alias="sessionNumber", description="Which session the issue belongs to.")
    ]
    update_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="updateDate", description="When the issue was last updated.")
    ]
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the issue record in the API.")
    ] = None
    volume_number: Annotated[
        Optional[int | str],
        Field(default=None, alias="volumeNumber", description="What the volume number is.")
    ]


class BoundCongressionalRecordListItem(BaseModel):
    """List-level bound congressional record entry."""
    date: Annotated[
        Optional[datetime],
        Field(description="When the bound record was published.")
    ] = None
    volume_number: Annotated[
        Optional[int | str],
        Field(default=None, alias="volumeNumber", description="What the volume number is.")
    ]
    congress: Annotated[
        Optional[int | str],
        Field(description="Which Congress the bound record belongs to.")
    ] = None
    session_number: Annotated[
        Optional[int | str],
        Field(default=None, alias="sessionNumber", description="Which session the record belongs to.")
    ]
    update_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="updateDate", description="When the bound record was last updated.")
    ]
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the bound record in the API.")
    ] = None


class CongressionalRecordIssue(BaseModel):
    """Issue metadata from the Congressional Record feed."""
    congress: Annotated[
        Optional[str],
        Field(default=None, alias="Congress", description="Which Congress the issue belongs to.")
    ]
    id: Annotated[
        Optional[int],
        Field(default=None, alias="Id", description="What the issue identifier is.")
    ]
    issue: Annotated[
        Optional[str],
        Field(default=None, alias="Issue", description="What the issue number is.")
    ]
    links: Annotated[
        Optional[dict[str, Any]],
        Field(default=None, alias="Links", description="What related links are provided for the issue.")
    ]
    publish_date: Annotated[
        Optional[str],
        Field(default=None, alias="PublishDate", description="When the issue was published.")
    ]
    session: Annotated[
        Optional[str],
        Field(default=None, alias="Session", description="Which session the issue belongs to.")
    ]
    volume: Annotated[
        Optional[str],
        Field(default=None, alias="Volume", description="What the volume number is.")
    ]


class CommitteeListItem(BaseModel):
    """List-level committee entry with system code and metadata."""
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the committee in the API.")
    ] = None
    system_code: Annotated[
        Optional[str],
        Field(default=None, alias="systemCode", description="What the committee system code is.")
    ]
    name: Annotated[
        Optional[str],
        Field(description="What the committee name is.")
    ] = None
    chamber: Annotated[
        Optional[str],
        Field(description="Which chamber the committee belongs to.")
    ] = None
    committee_type_code: Annotated[
        Optional[str],
        Field(default=None, alias="committeeTypeCode", description="What the committee type code is.")
    ]
    update_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="updateDate", description="When the committee was last updated.")
    ]


class CommitteeReportListItem(BaseModel):
    """List-level committee report entry with citation metadata."""
    citation: Annotated[
        Optional[str],
        Field(description="What the committee report citation is.")
    ] = None
    cmte_rpt_id: Annotated[
        Optional[int],
        Field(default=None, alias="cmte_rpt_id", description="What the committee report identifier is.")
    ]
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the report in the API.")
    ] = None
    update_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="updateDate", description="When the report was last updated.")
    ]
    congress: Annotated[
        Optional[int],
        Field(description="Which Congress the report belongs to.")
    ] = None
    chamber: Annotated[
        Optional[str],
        Field(description="Which chamber issued the report.")
    ] = None
    type: Annotated[
        Optional[str],
        Field(description="What type of committee report this is.")
    ] = None
    number: Annotated[
        Optional[int],
        Field(description="What the report number is.")
    ] = None
    part: Annotated[
        Optional[int],
        Field(description="Which part of a multi-part report this is.")
    ] = None


class AmendmentLatestAction(BaseModel):
    """Latest action metadata attached to an amendment list item."""
    action_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="actionDate", description="When the latest action occurred.")
    ]
    action_time: Annotated[
        Optional[str],
        Field(default=None, alias="actionTime", description="What time the latest action occurred.")
    ]
    text: Annotated[
        Optional[str],
        Field(description="What the latest action text says.")
    ] = None


class AmendmentListItem(BaseModel):
    """List-level amendment entry with latest action and type."""
    congress: Annotated[
        Optional[int],
        Field(description="Which Congress the amendment belongs to.")
    ] = None
    description: Annotated[
        Optional[str],
        Field(description="What the amendment description says.")
    ] = None
    latest_action: Annotated[
        Optional[AmendmentLatestAction],
        Field(default=None, alias="latestAction", description="What the latest action is.")
    ]
    number: Annotated[
        Optional[str],
        Field(description="What the amendment number is.")
    ] = None
    purpose: Annotated[
        Optional[str],
        Field(description="What purpose the amendment states.")
    ] = None
    type: Annotated[
        Optional[str],
        Field(description="What type of amendment this is.")
    ] = None
    update_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="updateDate", description="When the amendment was last updated.")
    ]
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the amendment in the API.")
    ] = None


class BillLatestAction(BaseModel):
    """Latest action metadata attached to a bill list item."""
    action_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="actionDate", description="When the latest action occurred.")
    ]
    text: Annotated[
        Optional[str],
        Field(description="What the latest action text says.")
    ] = None


class LawEntry(BaseModel):
    """Law entry used in law list items (number and type)."""
    number: Annotated[
        Optional[str],
        Field(description="What the law number is.")
    ] = None
    type: Annotated[
        Optional[str],
        Field(description="What type of law this is (public/private).")
    ] = None


class BillListItem(BaseModel):
    """List-level bill entry with title and latest action."""
    congress: Annotated[
        Optional[int],
        Field(description="Which Congress the bill belongs to.")
    ] = None
    latest_action: Annotated[
        Optional[BillLatestAction],
        Field(default=None, alias="latestAction", description="What the latest action is.")
    ]
    number: Annotated[
        Optional[str],
        Field(description="What the bill number is.")
    ] = None
    origin_chamber: Annotated[
        Optional[str],
        Field(default=None, alias="originChamber", description="Which chamber introduced the bill.")
    ]
    origin_chamber_code: Annotated[
        Optional[str],
        Field(default=None, alias="originChamberCode", description="What the origin chamber code is.")
    ]
    title: Annotated[
        Optional[str],
        Field(description="What the bill title is.")
    ] = None
    type: Annotated[
        Optional[str],
        Field(description="What type of bill this is.")
    ] = None
    update_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="updateDate", description="When the bill was last updated.")
    ]
    update_date_including_text: Annotated[
        Optional[datetime],
        Field(default=None, alias="updateDateIncludingText", description="When the bill or its text was last updated.")
    ]
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the bill in the API.")
    ] = None


class LawListItem(BaseModel):
    """List-level law entry derived from bill data."""
    congress: Annotated[
        Optional[int],
        Field(description="Which Congress the law belongs to.")
    ] = None
    latest_action: Annotated[
        Optional[BillLatestAction],
        Field(default=None, alias="latestAction", description="What the latest action is.")
    ]
    laws: Annotated[
        Optional[List[LawEntry]],
        Field(description="Which law entries are associated with the bill.")
    ] = None
    number: Annotated[
        Optional[str],
        Field(description="What the bill number is.")
    ] = None
    origin_chamber: Annotated[
        Optional[str],
        Field(default=None, alias="originChamber", description="Which chamber introduced the bill.")
    ]
    origin_chamber_code: Annotated[
        Optional[str],
        Field(default=None, alias="originChamberCode", description="What the origin chamber code is.")
    ]
    title: Annotated[
        Optional[str],
        Field(description="What the bill title is.")
    ] = None
    type: Annotated[
        Optional[str],
        Field(description="What type of bill this is.")
    ] = None
    update_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="updateDate", description="When the law record was last updated.")
    ]
    update_date_including_text: Annotated[
        Optional[datetime],
        Field(default=None, alias="updateDateIncludingText", description="When the law or its text was last updated.")
    ]
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the law in the API.")
    ] = None


class CommitteePrintListItem(BaseModel):
    """List-level committee print entry."""
    jacket_number: Annotated[
        Optional[int],
        Field(default=None, alias="jacketNumber", description="What the jacket number is.")
    ]
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the committee print in the API.")
    ] = None
    update_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="updateDate", description="When the committee print was last updated.")
    ]
    congress: Annotated[
        Optional[int],
        Field(description="Which Congress the committee print belongs to.")
    ] = None
    chamber: Annotated[
        Optional[str],
        Field(description="Which chamber the committee print belongs to.")
    ] = None


class CommitteeMeetingListItem(BaseModel):
    """List-level committee meeting entry."""
    event_id: Annotated[
        Optional[int],
        Field(default=None, alias="eventId", description="What the meeting event identifier is.")
    ]
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the meeting in the API.")
    ] = None
    update_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="updateDate", description="When the meeting was last updated.")
    ]
    congress: Annotated[
        Optional[int],
        Field(description="Which Congress the meeting belongs to.")
    ] = None
    chamber: Annotated[
        Optional[str],
        Field(description="Which chamber the meeting belongs to.")
    ] = None


class HearingListItem(BaseModel):
    """List-level hearing entry with jacket number and metadata."""
    jacket_number: Annotated[
        Optional[int],
        Field(default=None, alias="jacketNumber", description="What the hearing jacket number is.")
    ]
    update_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="updateDate", description="When the hearing was last updated.")
    ]
    chamber: Annotated[
        Optional[str],
        Field(description="Which chamber held the hearing.")
    ] = None
    congress: Annotated[
        Optional[int],
        Field(description="Which Congress the hearing belongs to.")
    ] = None
    number: Annotated[
        Optional[int],
        Field(description="What the hearing number is.")
    ] = None
    part: Annotated[
        Optional[int],
        Field(description="Which part of a multipart hearing this is.")
    ] = None
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the hearing in the API.")
    ] = None


class TreatyListItem(BaseModel):
    """List-level treaty entry with congress and numbering info."""
    congress_received: Annotated[
        Optional[int],
        Field(default=None, alias="congressReceived", description="Which Congress received the treaty.")
    ]
    congress_considered: Annotated[
        Optional[int],
        Field(default=None, alias="congressConsidered", description="Which Congress considered the treaty.")
    ]
    number: Annotated[
        Optional[int],
        Field(description="What the treaty number is.")
    ] = None
    parts: Annotated[
        Optional[dict[str, Any]],
        Field(description="What parts the treaty is divided into.")
    ] = None
    suffix: Annotated[
        Optional[str],
        Field(description="What suffix the treaty carries.")
    ] = None
    topic: Annotated[
        Optional[str],
        Field(description="What topic the treaty concerns.")
    ] = None
    transmitted_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="transmittedDate", description="When the treaty was transmitted.")
    ]
    update_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="updateDate", description="When the treaty was last updated.")
    ]
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the treaty in the API.")
    ] = None


class MemberListItem(BaseModel):
    """List-level member entry with name, party, and term data."""
    bioguide_id: Annotated[
        str,
        Field(alias="bioguideId", description="What the member's Bioguide identifier is.")
    ]
    state: Annotated[
        Optional[str],
        Field(description="Which state or territory the member represents.")
    ] = None
    party_name: Annotated[
        Optional[str],
        Field(default=None, alias="partyName", description="What the member's party name is.")
    ]
    district: Annotated[
        Optional[int],
        Field(description="Which congressional district the member represents.")
    ] = None
    name: Annotated[
        Optional[str],
        Field(description="What the member's display name is.")
    ] = None
    depiction: Annotated[
        Optional[MemberDepiction],
        Field(description="What image information is available for the member.")
    ] = None
    terms: Annotated[
        Optional[MemberTerms],
        Field(description="Which terms are listed for the member.")
    ] = None
    update_date: Annotated[
        Optional[datetime],
        Field(default=None, alias="updateDate", description="When the member record was last updated.")
    ]
    url: Annotated[
        Optional[HttpUrl],
        Field(description="Where to retrieve the member record in the API.")
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
            raise TypeError('CommitteeCode must be a string')
        if not re.fullmatch(r'[a-zA-Z]{4}\d{2}', v):
            raise ValueError(f"CommitteeCode '{v}' must match pattern: 4 alpha + 2 digits (e.g., 'hspw00')")
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
    requirement_number: Annotated[int, Field(description="What the requirement number is.")]

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
    communication_number: Annotated[int, Field(description="What the communication number is.")]

class NominationNumber(BaseModel):
    """Wrapper for nomination numbers in endpoint parameters."""
    """
    The assigned nomination number (Presidential Nomination).
    """
    nomination_number: Annotated[int, Field(description="What the nomination number is.")]

class TreatyNumber(BaseModel):
    """Wrapper for treaty numbers in endpoint parameters."""
    """
    The assigned treaty number.
    """
    treaty_number: Annotated[int, Field(description="What the treaty number is.")]

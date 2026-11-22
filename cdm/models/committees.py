"""Committee and hearing related list models."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, HttpUrl

from cdm.models.shared import EntityBase
from cdm.models.taxonomy import RecordTypeBase


class CommitteeListItem(EntityBase, RecordTypeBase):
    """List-level committee entry with system code and metadata."""

    recordType: str = Field(
        default="congress-committees",
        description="Which knowledgebase index this record belongs to.",
    )
    url: HttpUrl | None = Field(
        default=None, description="Where to retrieve the committee in the API."
    )
    system_code: str | None = Field(
        default=None,
        alias="systemCode",
        description="What the committee system code is.",
    )
    name: str | None = Field(
        default=None, description="What the committee name is."
    )
    chamber: str | None = Field(
        default=None, description="Which chamber the committee belongs to."
    )
    committee_type_code: str | None = Field(
        default=None,
        alias="committeeTypeCode",
        description="What the committee type code is.",
    )
    update_date: datetime | None = Field(
        default=None,
        alias="updateDate",
        description="When the committee was last updated.",
    )
    subcommittees: list[dict] | None = None


class CommitteeReportListItem(EntityBase, RecordTypeBase):
    """List-level committee report entry with citation metadata."""

    recordType: str = Field(
        default="congress-committee-reports",
        description="Which knowledgebase index this record belongs to.",
    )
    citation: str | None = Field(
        default=None, description="What the committee report citation is."
    )
    cmte_rpt_id: int | None = Field(
        default=None,
        alias="cmte_rpt_id",
        description="What the committee report identifier is.",
    )
    url: HttpUrl | None = Field(
        default=None, description="Where to retrieve the report in the API."
    )
    update_date: datetime | None = Field(
        default=None,
        alias="updateDate",
        description="When the report was last updated.",
    )
    congress: int | None = Field(
        default=None, description="Which Congress the report belongs to."
    )
    chamber: str | None = Field(
        default=None, description="Which chamber issued the report."
    )
    type: str | None = Field(
        default=None, description="What type of committee report this is."
    )
    number: int | None = Field(
        default=None, description="What the report number is."
    )
    part: int | None = Field(
        default=None, description="Which part of a multi-part report this is."
    )


class CommitteePrintListItem(EntityBase, RecordTypeBase):
    """List-level committee print entry."""

    recordType: str = Field(
        default="congress-committee-prints",
        description="Which knowledgebase index this record belongs to.",
    )
    jacket_number: int | None = Field(
        default=None, alias="jacketNumber", description="What the jacket number is."
    )
    url: HttpUrl | None = Field(
        default=None, description="Where to retrieve the committee print in the API."
    )
    update_date: datetime | None = Field(
        default=None,
        alias="updateDate",
        description="When the committee print was last updated.",
    )
    congress: int | None = Field(
        default=None, description="Which Congress the committee print belongs to."
    )
    chamber: str | None = Field(
        default=None, description="Which chamber the committee print belongs to."
    )


class CommitteeMeetingListItem(EntityBase, RecordTypeBase):
    """List-level committee meeting entry."""

    recordType: str = Field(
        default="congress-committee-meetings",
        description="Which knowledgebase index this record belongs to.",
    )
    event_id: int | None = Field(
        default=None,
        alias="eventId",
        description="What the meeting event identifier is.",
    )
    url: HttpUrl | None = Field(
        default=None, description="Where to retrieve the meeting in the API."
    )
    update_date: datetime | None = Field(
        default=None,
        alias="updateDate",
        description="When the meeting was last updated.",
    )
    congress: int | None = Field(
        default=None, description="Which Congress the meeting belongs to."
    )
    chamber: str | None = Field(
        default=None, description="Which chamber the meeting belongs to."
    )


class HearingListItem(EntityBase, RecordTypeBase):
    """List-level hearing entry with jacket number and metadata."""

    recordType: str = Field(
        default="congress-hearings",
        description="Which knowledgebase index this record belongs to.",
    )
    jacket_number: int | None = Field(
        default=None,
        alias="jacketNumber",
        description="What the hearing jacket number is.",
    )
    update_date: datetime | None = Field(
        default=None,
        alias="updateDate",
        description="When the hearing was last updated.",
    )
    chamber: str | None = Field(
        default=None, description="Which chamber held the hearing."
    )
    congress: int | None = Field(
        default=None, description="Which Congress the hearing belongs to."
    )
    number: int | None = Field(
        default=None, description="What the hearing number is."
    )
    part: int | None = Field(
        default=None, description="Which part of a multipart hearing this is."
    )
    url: HttpUrl | None = Field(
        default=None, description="Where to retrieve the hearing in the API."
    )


__all__ = [
    "CommitteeListItem",
    "CommitteeMeetingListItem",
    "CommitteePrintListItem",
    "CommitteeReportListItem",
    "HearingListItem",
]

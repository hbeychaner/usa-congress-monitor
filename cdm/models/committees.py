"""Committee and hearing related list models."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, HttpUrl

from cdm.models.shared import EntityBase
from cdm.models.taxonomy import RecordTypeBase


class CommitteeListItem(EntityBase, RecordTypeBase):
    """List-level committee entry with system code and metadata."""

    recordType: str = "congress-committees"
    url: HttpUrl | None = None
    system_code: str | None = Field(default=None, alias="systemCode")
    name: str | None = None
    chamber: str | None = None
    committee_type_code: str | None = Field(default=None, alias="committeeTypeCode")
    update_date: datetime | None = Field(default=None, alias="updateDate")
    subcommittees: list[dict] | None = None


class CommitteeReportListItem(EntityBase, RecordTypeBase):
    """List-level committee report entry with citation metadata."""

    recordType: str = "congress-committee-reports"
    citation: str | None = None
    cmte_rpt_id: int | None = Field(default=None, alias="cmte_rpt_id")
    url: HttpUrl | None = None
    update_date: datetime | None = Field(default=None, alias="updateDate")
    congress: int | None = None
    chamber: str | None = None
    type: str | None = None
    number: int | None = None
    part: int | None = None


class CommitteePrintListItem(EntityBase, RecordTypeBase):
    """List-level committee print entry."""

    recordType: str = "congress-committee-prints"
    jacket_number: int | None = Field(default=None, alias="jacketNumber")
    url: HttpUrl | None = None
    update_date: datetime | None = Field(default=None, alias="updateDate")
    congress: int | None = None
    chamber: str | None = None


class CommitteeMeetingListItem(EntityBase, RecordTypeBase):
    """List-level committee meeting entry."""

    recordType: str = "congress-committee-meetings"
    event_id: int | None = Field(default=None, alias="eventId")
    url: HttpUrl | None = None
    update_date: datetime | None = Field(default=None, alias="updateDate")
    congress: int | None = None
    chamber: str | None = None


class HearingListItem(EntityBase, RecordTypeBase):
    """List-level hearing entry with jacket number and metadata."""

    recordType: str = "congress-hearings"
    jacket_number: int | None = Field(default=None, alias="jacketNumber")
    update_date: datetime | None = Field(default=None, alias="updateDate")
    chamber: str | None = None
    congress: int | None = None
    number: int | None = None
    part: int | None = None
    url: HttpUrl | None = None


__all__ = [
    "CommitteeListItem",
    "CommitteeMeetingListItem",
    "CommitteePrintListItem",
    "CommitteeReportListItem",
    "HearingListItem",
]

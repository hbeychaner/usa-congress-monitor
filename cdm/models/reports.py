"""Report and summary-related models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, model_validator

from cdm.models.shared import EntityBase
from cdm.models.taxonomy import RecordTypeBase, Topic


class CRSReport(EntityBase):
    """Congressional Research Service report metadata and summary."""

    title: str
    publish_date: datetime | None = Field(default=None, alias="publishDate")
    publish_date_raw: str | None = Field(default=None, alias="publish_date")
    content_type: str | None = Field(default=None, alias="contentType")
    version: int | str | None = None
    update_date: datetime | None = Field(default=None, alias="updateDate")
    url: HttpUrl | None = None
    status: str | None = None
    summary: str | None = None
    authors: list[str] | None = None
    topics: list[Topic] | None = None

    @model_validator(mode="before")
    def _normalize_input(cls, values: dict):
        url = values.get("url")
        if isinstance(url, str) and url.startswith("www."):
            values["url"] = f"https://{url}"

        authors = values.get("authors")
        if isinstance(authors, list):
            values["authors"] = [
                a.get("author") if isinstance(a, dict) and "author" in a else a
                for a in authors
                if (isinstance(a, dict) and "author" in a) or isinstance(a, str)
            ]

        if values.get("publishDate") and not values.get("publish_date"):
            values["publish_date"] = values.get("publishDate")

        return values


class CRSReportListItem(EntityBase, RecordTypeBase):
    """List-level CRS report entry with status and metadata."""

    recordType: str = "congress-crs-reports"
    status: str | None = None
    publish_date: datetime | None = Field(default=None, alias="publishDate")
    version: int | str | None = None
    content_type: str | None = Field(default=None, alias="contentType")
    update_date: datetime | None = Field(default=None, alias="updateDate")
    title: str | None = None
    url: HttpUrl | None = None


class BillSummaryBill(BaseModel):
    """Bill reference embedded in a summary list item."""

    congress: int
    type: str
    origin_chamber: str | None = Field(default=None, alias="originChamber")
    origin_chamber_code: str | None = Field(default=None, alias="originChamberCode")
    number: int
    url: HttpUrl | None = None
    title: str | None = None
    update_date_including_text: datetime | None = Field(
        default=None, alias="updateDateIncludingText"
    )


class BillSummaryListItem(EntityBase, RecordTypeBase):
    """List-level bill summary entry with action and version details."""

    recordType: str = "congress-summaries"
    bill: BillSummaryBill
    text: str | None = None
    action_date: datetime | None = Field(default=None, alias="actionDate")
    update_date: datetime | None = Field(default=None, alias="updateDate")
    current_chamber: str | None = Field(default=None, alias="currentChamber")
    current_chamber_code: str | None = Field(default=None, alias="currentChamberCode")
    action_desc: str | None = Field(default=None, alias="actionDesc")
    version_code: str | None = Field(default=None, alias="versionCode")
    last_summary_update_date: datetime | None = Field(
        default=None, alias="lastSummaryUpdateDate"
    )


__all__ = [
    "BillSummaryBill",
    "BillSummaryListItem",
    "CRSReport",
    "CRSReportListItem",
]

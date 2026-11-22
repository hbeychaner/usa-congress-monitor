"""Report and summary-related models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, model_validator

from cdm.models.shared import EntityBase
from cdm.models.taxonomy import RecordTypeBase, Topic


class CRSReport(EntityBase):
    """Congressional Research Service report metadata and summary."""

    title: str = Field(description="What the CRS report title is.")
    publish_date: datetime | None = Field(
        default=None,
        alias="publishDate",
        description="When the CRS report was published.",
    )
    publish_date_raw: str | None = Field(default=None, alias="publish_date")
    content_type: str | None = Field(default=None, alias="contentType")
    version: int | str | None = None
    update_date: datetime | None = Field(default=None, alias="updateDate")
    url: HttpUrl | None = Field(
        default=None, description="Where to retrieve the CRS report in the API."
    )
    status: str | None = Field(
        default=None, description="What the current status of the CRS report is."
    )
    summary: str | None = Field(
        default=None, description="What summary text the report provides."
    )
    authors: list[str] | None = Field(
        default=None, description="Who authored the CRS report."
    )
    topics: list[Topic] | None = Field(
        default=None, description="Which topics the CRS report covers."
    )

    @model_validator(mode="before")
    def _normalize_input(cls, values: dict):
        url = values.get("url")
        if isinstance(url, str) and url.startswith("www."):
            values["url"] = f"https://{url}"

        authors = values.get("authors")
        if isinstance(authors, list):
            normalized = []
            for a in authors:
                if isinstance(a, dict) and "author" in a:
                    normalized.append(a.get("author"))
                elif isinstance(a, str):
                    normalized.append(a)
            values["authors"] = normalized

        if values.get("publishDate") and not values.get("publish_date"):
            values["publish_date"] = values.get("publishDate")

        return values


class CRSReportListItem(EntityBase, RecordTypeBase):
    """List-level CRS report entry with status and metadata."""

    recordType: str = Field(
        default="congress-crs-reports",
        description="Which knowledgebase index this record belongs to.",
    )
    status: str | None = Field(
        default=None, description="What the CRS report status is."
    )
    publish_date: datetime | None = Field(
        default=None,
        alias="publishDate",
        description="When the report was published.",
    )
    version: int | str | None = Field(
        default=None, description="Which version of the report this is."
    )
    content_type: str | None = Field(
        default=None,
        alias="contentType",
        description="What content type the report is.",
    )
    update_date: datetime | None = Field(
        default=None,
        alias="updateDate",
        description="When the report was last updated.",
    )
    title: str | None = Field(default=None, description="What the report title is.")
    url: HttpUrl | None = Field(
        default=None, description="Where to retrieve the report in the API."
    )


class BillSummaryBill(BaseModel):
    """Bill reference embedded in a summary list item."""

    congress: int = Field(description="Which Congress the bill belongs to.")
    type: str = Field(description="What type of bill this is.")
    origin_chamber: str | None = Field(
        default=None,
        alias="originChamber",
        description="Which chamber introduced the bill.",
    )
    origin_chamber_code: str | None = Field(
        default=None,
        alias="originChamberCode",
        description="What the origin chamber code is.",
    )
    number: int = Field(description="What the bill number is.")
    url: HttpUrl | None = Field(
        default=None, description="Where to retrieve the bill record in the API."
    )
    title: str | None = Field(default=None, description="What the bill title is.")
    update_date_including_text: datetime | None = Field(
        default=None,
        alias="updateDateIncludingText",
        description="When the bill or its text was last updated.",
    )


class BillSummaryListItem(EntityBase, RecordTypeBase):
    """List-level bill summary entry with action and version details."""

    recordType: str = Field(
        default="congress-summaries",
        description="Which knowledgebase index this record belongs to.",
    )
    bill: BillSummaryBill = Field(description="Which bill the summary applies to.")
    text: str | None = Field(
        default=None, description="What the summary text says."
    )
    action_date: datetime | None = Field(
        default=None,
        alias="actionDate",
        description="When the summary action occurred.",
    )
    update_date: datetime | None = Field(
        default=None,
        alias="updateDate",
        description="When the summary was last updated.",
    )
    current_chamber: str | None = Field(
        default=None,
        alias="currentChamber",
        description="Which chamber the summary references.",
    )
    current_chamber_code: str | None = Field(
        default=None,
        alias="currentChamberCode",
        description="What the chamber code is for the summary.",
    )
    action_desc: str | None = Field(
        default=None,
        alias="actionDesc",
        description="What the summary action describes.",
    )
    version_code: str | None = Field(
        default=None,
        alias="versionCode",
        description="Which version of the summary this is.",
    )
    last_summary_update_date: datetime | None = Field(
        default=None,
        alias="lastSummaryUpdateDate",
        description="When the summary was last updated at the source.",
    )


__all__ = [
    "BillSummaryBill",
    "BillSummaryListItem",
    "CRSReport",
    "CRSReportListItem",
]

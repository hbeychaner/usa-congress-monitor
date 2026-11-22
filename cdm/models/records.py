"""Congressional record list models."""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import AliasChoices, BaseModel, Field, HttpUrl, model_validator

from cdm.data_collection.id_utils import UrlIdParser
from cdm.models.shared import CountUrl, EntityBase, Format
from cdm.models.taxonomy import RecordTypeBase

logger = logging.getLogger(__name__)


def _extract_date_parts(dt: object) -> tuple[str, str, str] | None:
    """Extract (year, month, day) strings from an ISO date string or date/datetime."""
    try:
        if isinstance(dt, str) and dt:
            parts = dt.split("T")[0].split("-")
            if len(parts) >= 3:
                return parts[0], parts[1], parts[2]
        elif hasattr(dt, "year") and dt:
            return str(dt.year), str(dt.month), str(dt.day)
    except (AttributeError, TypeError, ValueError):
        logger.exception("Failed to parse date components")
    return None


def _normalize_page_keys(target: dict) -> None:
    """Move camelCase startPage/endPage keys to snake_case in place."""
    if target.get("startPage") and not target.get("start_page"):
        target["start_page"] = target["startPage"]
    if target.get("endPage") and not target.get("end_page"):
        target["end_page"] = target["endPage"]
    target.pop("startPage", None)
    target.pop("endPage", None)


class Section(BaseModel):
    """Section entry within a bound congressional record issue."""

    start_page: int | None = Field(default=None, alias="startPage")
    end_page: int | None = Field(default=None, alias="endPage")
    title: str | None = Field(default=None, alias="title")
    ordinal: int | None = Field(default=None, alias="ordinal")

    model_config = {"populate_by_name": True}


Sections = list[Section]


class EntireIssueEntry(BaseModel):
    """Entry in `fullIssue.entireIssue` (e.g. PDF or formatted text part)."""

    part: int | None = Field(default=None, alias="part")
    type: str | None = Field(default=None, alias="type")
    url: HttpUrl | None = Field(default=None, alias="url")

    @model_validator(mode="before")
    def _coerce_part_to_int(cls, values: dict):
        p = values.get("part")
        if p is not None and not isinstance(p, int):
            try:
                values["part"] = (
                    int(p) if isinstance(p, str) and p.isdigit() else int(str(p))
                )
            except Exception:
                logger.exception("Failed to coerce entireIssue.part to int")
        return values


class DailySection(BaseModel):
    """Section entry used in `fullIssue.sections` for daily congressional record."""

    start_page: str | None = Field(default=None, alias="startPage")
    end_page: str | None = Field(default=None, alias="endPage")
    name: str | None = Field(default=None, alias="name")
    text: list[Format] | None = Field(default=None, alias="text")

    model_config = {"populate_by_name": True}


class FullIssue(BaseModel):
    """Container for the `fullIssue` payload returned by the API."""

    articles: CountUrl | None = Field(default=None, alias="articles")
    entire_issue: list[EntireIssueEntry] | None = Field(
        default=None, alias="entireIssue"
    )
    sections: list[DailySection] | None = Field(default=None, alias="sections")

    model_config = {"populate_by_name": True}


class DailyCongressionalRecordIssue(EntityBase, RecordTypeBase):
    """List-level daily congressional record issue entry."""

    recordType: str = "congress-daily-congressional-records"
    congress: int | None = None
    issue_date: datetime | None = Field(default=None, alias="issueDate")
    issue_number: int | str | None = Field(default=None, alias="issueNumber")
    session_number: int | str | None = Field(default=None, alias="sessionNumber")
    update_date: datetime | None = Field(default=None, alias="updateDate")
    url: HttpUrl | None = None
    full_issue: FullIssue | None = Field(default=None, alias="fullIssue")
    volume_number: int | str | None = Field(default=None, alias="volumeNumber")
    issue: dict | None = Field(default=None, alias="issue")

    def build_id(self) -> str:
        """Build deterministic id from `volume_number` + `issue_number` when possible."""
        if getattr(self, "id", None):
            return str(self.id)

        vol = getattr(self, "volume_number", None) or getattr(
            self, "volumeNumber", None
        )
        issue = getattr(self, "issue_number", None) or getattr(
            self, "issueNumber", None
        )
        if vol is not None and issue is not None:
            try:
                return f"daily-congressional-record:{int(vol)}:{int(issue)}"
            except (TypeError, ValueError):
                logger.exception("Failed to coerce volume/issue to int for id build")
                return f"daily-congressional-record:{vol}:{issue}"

        return super().build_id()


class BoundCongressionalRecordListItem(EntityBase, RecordTypeBase):
    """List-level bound congressional record entry."""

    recordType: str = "congress-bound-congressional-records"
    date: datetime | None = None
    volume_number: int | str | None = Field(default=None, alias="volumeNumber")
    congress: int | str | None = None
    session_number: int | str | None = Field(default=None, alias="sessionNumber")
    update_date: datetime | None = Field(default=None, alias="updateDate")
    sections: Sections | None = Field(default=None, alias="sections")
    daily_digest: dict | None = Field(default=None, alias="dailyDigest")
    url: HttpUrl | None = None
    reference_id: str | None = Field(
        default=None,
        alias="reference_id",
        validation_alias=AliasChoices("reference_id", "referenceId"),
    )

    @model_validator(mode="before")
    def _normalize_bound_record_fields(cls, values: dict):
        dd = (
            values.get("dailyDigest")
            if "dailyDigest" in values
            else values.get("daily_digest")
        )
        normalized: dict | None = None
        if dd is not None and not isinstance(dd, dict):
            try:
                if isinstance(dd, list) and dd:
                    first = dd[0]
                    normalized = first if isinstance(first, dict) else {"value": first}
                elif isinstance(dd, str):
                    normalized = {"summary": dd}
                else:
                    normalized = {"value": str(dd)}
            except (AttributeError, IndexError, TypeError, ValueError):
                normalized = None
        elif isinstance(dd, dict):
            normalized = dd

        if isinstance(normalized, dict):
            _normalize_page_keys(normalized)
            values["daily_digest"] = normalized
            values["dailyDigest"] = normalized

        if values.get("recordType") and not values.get("record_type"):
            values["record_type"] = values["recordType"]
        values.pop("recordType", None)

        _normalize_page_keys(values)

        secs = values.get("sections")
        if isinstance(secs, list):
            for s in secs:
                if isinstance(s, dict):
                    _normalize_page_keys(s)

        if values.get("referenceId") and not values.get("reference_id"):
            values["reference_id"] = values["referenceId"]
        values.pop("referenceId", None)

        if values.get("dailyDigest") and not values.get("daily_digest"):
            values["daily_digest"] = values["dailyDigest"]

        return values

    @model_validator(mode="before")
    def _populate_url_from_date(cls, values: dict):
        if values.get("url"):
            return values
        parts = _extract_date_parts(values.get("date"))
        if parts:
            year, month, day = parts
            values["url"] = (
                f"https://api.congress.gov/v3/bound-congressional-record/{year}/{int(month)}/{int(day)}?format=json"
            )
        return values

    @model_validator(mode="before")
    def _populate_reference_id_from_url(cls, values: dict):
        if not values.get("reference_id") and values.get("url"):
            try:
                values["reference_id"] = UrlIdParser.parse(str(values.get("url")))
            except (TypeError, ValueError):
                logger.exception("Failed to parse reference id from URL")
        return values

    def build_id(self) -> str:
        """Build a deterministic id from the `date` when `id` is missing."""
        if getattr(self, "id", None):
            return str(self.id)

        parts = _extract_date_parts(getattr(self, "date", None))
        if parts:
            year, month, day = parts
            try:
                base = f"bound-congressional-record:{year}:{int(month)}:{int(day)}"
                sp = ep = None
                secs = getattr(self, "sections", None) or []
                if isinstance(secs, list) and secs:
                    first = secs[0]
                    if isinstance(first, dict):
                        sp = first.get("start_page") or first.get("startPage")
                        ep = first.get("end_page") or first.get("endPage")
                    else:
                        sp = getattr(first, "start_page", None) or getattr(
                            first, "startPage", None
                        )
                        ep = getattr(first, "end_page", None) or getattr(
                            first, "endPage", None
                        )
                if (sp is None or ep is None) and isinstance(
                    getattr(self, "daily_digest", None), dict
                ):
                    dd = self.daily_digest or {}
                    sp = dd.get("start_page") or dd.get("startPage")
                    ep = dd.get("end_page") or dd.get("endPage")
                if sp is not None and ep is not None:
                    try:
                        return f"{base}:{int(sp)}:{int(ep)}"
                    except (TypeError, ValueError):
                        return base
                return base
            except (AttributeError, TypeError, ValueError):
                logger.exception(
                    "Unexpected error while building bound congressional record id"
                )

        return super().build_id()


class CongressionalRecordIssue(EntityBase, RecordTypeBase):
    """Issue metadata from the Congressional Record feed."""

    recordType: str = "congress-congressional-records"
    congress: str | None = Field(default=None, alias="Congress")
    source_id: int | None = Field(default=None, alias="Id")
    issue: str | None = Field(default=None, alias="Issue")
    links: dict[str, object] | None = Field(default=None, alias="Links")
    publish_date: str | None = Field(default=None, alias="PublishDate")
    session: str | None = Field(default=None, alias="Session")
    volume: str | None = Field(default=None, alias="Volume")


__all__ = [
    "BoundCongressionalRecordListItem",
    "CongressionalRecordIssue",
    "DailyCongressionalRecordIssue",
    "DailySection",
    "EntireIssueEntry",
    "FullIssue",
    "Section",
    "Sections",
]

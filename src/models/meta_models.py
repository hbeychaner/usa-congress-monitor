"""Meta and response Pydantic models used by the ingest pipeline.

Small, focused models used to coerce chunk/meta payloads and parse
API responses for spec-driven consumers.
"""

from __future__ import annotations

from typing import List, Optional, Mapping

from pydantic import BaseModel, ConfigDict, Field

from src.models.other_models import (
    AmendmentListItem,
    BillListItem,
    BillSummaryListItem,
    CommitteeListItem,
    CommitteeMeetingListItem,
    CommitteePrintListItem,
    CommitteeReportListItem,
    CRSReport,
    HearingListItem,
    HouseCommunicationListItem,
    HouseRequirementListItem,
    MemberListItem,
    NominationListItem,
    SenateCommunicationListItem,
    TreatyListItem,
)


class BaseChunkMeta(BaseModel):
    """Base metadata for paginated chunked fetch operations.

    Fields:
        offset: Pagination offset for the request.
        limit: Requested page size or limit.
    """

    offset: int = Field(0, description="Offset for paginated endpoints")
    limit: int = Field(250, description="Limit/page size for paginated endpoints")
    model_config = ConfigDict(validate_by_name=True)


class GenericChunkMeta(BaseChunkMeta):
    """Generic chunk metadata used across many list endpoints.

    Extends :class:`BaseChunkMeta` with common filtering fields such as
    `congress`, `type`, date ranges, and pagination hints reported by APIs.
    """

    congress: Optional[int] = Field(None, description="Congress number")
    type: Optional[str] = Field(None, description="Record type or bill type")
    chamber: Optional[str] = Field(None, description="Chamber filter (house/senate)")
    from_date_time: Optional[str] = Field(
        None,
        alias="fromDateTime",
        description="Start datetime for date-filtered endpoints",
    )
    to_date_time: Optional[str] = Field(
        None, alias="toDateTime", description="End datetime for date-filtered endpoints"
    )
    year: Optional[int] = Field(None, description="Year for year-scoped endpoints")
    page: Optional[int] = Field(None, description="Page number from API metadata")
    page_size: Optional[int] = Field(
        None, alias="pageSize", description="Page size from API metadata"
    )
    total_pages: Optional[int] = Field(
        None, alias="totalPages", description="Total pages reported by API"
    )
    report_type: Optional[str] = Field(
        None, alias="reportType", description="Report type alias for API"
    )


class CommitteeReportMeta(GenericChunkMeta):
    """Specialized meta for committee reports (inherits generic chunk fields)."""


class BillMeta(GenericChunkMeta):
    """Meta model for bill endpoints. Inherits generic pagination and congress/type fields."""


class CRSReportMeta(GenericChunkMeta):
    """Meta model for CRS report endpoints (exposes `year`)."""


class CommitteeMeetingMeta(GenericChunkMeta):
    """Meta for committee meeting endpoints (congress + chamber)."""


class HearingMeta(GenericChunkMeta):
    """Meta for hearing endpoints (congress + chamber)."""


class AmendmentMeta(GenericChunkMeta):
    """Meta for amendment endpoints (inherits generic fields)."""


class CommitteeReportsResponse(BaseModel):
    """Wrapper for committee reports list responses."""

    reports: List[CommitteeReportListItem] = Field(
        default_factory=list, description="List of committee report items"
    )
    pagination: Optional[Mapping[str, object]] = None
    model_config = ConfigDict(validate_by_name=True)


class BillListResponse(BaseModel):
    """Wrapper for bill list responses."""

    bills: List[BillListItem] = Field(
        default_factory=list, description="List of bill items"
    )
    pagination: Optional[Mapping[str, object]] = None
    model_config = ConfigDict(validate_by_name=True)


class MemberListResponse(BaseModel):
    """Wrapper for member list responses."""

    members: List[MemberListItem] = Field(
        default_factory=list, description="List of member items"
    )
    pagination: Optional[Mapping[str, object]] = None
    model_config = ConfigDict(validate_by_name=True)


class CRSReportsResponse(BaseModel):
    """Wrapper for CRS report list responses."""

    CRSReports: List[CRSReport] = Field(
        default_factory=list, description="List of CRS report items"
    )
    pagination: Optional[Mapping[str, object]] = None
    model_config = ConfigDict(validate_by_name=True)


class CongressMeta(BaseChunkMeta):
    """Metadata specifically for endpoints scoped to a single Congress."""

    congress: Optional[int] = Field(None, description="Congress number")


class CongressListResponse(BaseModel):
    """Wrapper for congress list responses."""

    congresses: List[Mapping[str, object]] = Field(
        default_factory=list, description="List of congress items"
    )
    pagination: Optional[Mapping[str, object]] = None
    model_config = ConfigDict(validate_by_name=True)


class CommitteeListResponse(BaseModel):
    """Wrapper for committee list responses."""

    committees: List[CommitteeListItem] = Field(
        default_factory=list, description="List of committee items"
    )
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class NominationListResponse(BaseModel):
    """Wrapper for nomination list responses."""

    nominations: List[NominationListItem] = Field(
        default_factory=list, description="List of nomination items"
    )
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class BoundCongressionalRecordResponse(BaseModel):
    """Wrapper for bound congressional record list responses."""

    boundCongressionalRecord: List[Mapping[str, object]] = Field(
        default_factory=list, description="List of bound congressional record items"
    )
    pagination: Optional[Mapping[str, object]] = None
    model_config = ConfigDict(validate_by_name=True)


class DailyCongressionalRecordResponse(BaseModel):
    """Wrapper for daily congressional record list responses."""

    dailyCongressionalRecord: List[Mapping[str, object]] = Field(
        default_factory=list, description="List of daily congressional record items"
    )
    pagination: Optional[Mapping[str, object]] = None
    model_config = ConfigDict(validate_by_name=True)


class SummariesResponse(BaseModel):
    """Wrapper for bill summaries list responses."""

    summaries: List[BillSummaryListItem] = Field(
        default_factory=list, description="List of summary items"
    )
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class TreatyListResponse(BaseModel):
    """Wrapper for treaty list responses."""

    treaties: List[TreatyListItem] = Field(
        default_factory=list, description="List of treaty items"
    )
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class HouseRequirementsResponse(BaseModel):
    """Wrapper for house requirements list responses."""

    houseRequirements: List[HouseRequirementListItem] = Field(
        default_factory=list, description="List of house requirement items"
    )
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class HouseVotesResponse(BaseModel):
    """Wrapper for house roll-call vote list responses."""

    houseRollCallVotes: List[Mapping[str, object]] = Field(
        default_factory=list, description="List of house roll call vote items"
    )
    pagination: Optional[Mapping[str, object]] = None
    model_config = ConfigDict(validate_by_name=True)


class CommitteeMeetingsResponse(BaseModel):
    """Wrapper for committee meetings list responses."""

    committeeMeetings: List[CommitteeMeetingListItem] = Field(
        default_factory=list, description="List of committee meeting items"
    )
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class HearingsResponse(BaseModel):
    """Wrapper for hearings list responses."""

    hearings: List[HearingListItem] = Field(
        default_factory=list, description="List of hearing items"
    )
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class AmendmentsResponse(BaseModel):
    """Wrapper for amendment list responses."""

    amendments: List[AmendmentListItem] = Field(
        default_factory=list, description="List of amendment items"
    )
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class CommitteePrintsResponse(BaseModel):
    """Wrapper for committee prints list responses."""

    committeePrints: List["CommitteePrintListItem"] = Field(
        default_factory=list, description="List of committee print items"
    )
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class HouseCommunicationsResponse(BaseModel):
    """Wrapper for house communications list responses."""

    houseCommunications: List["HouseCommunicationListItem"] = Field(
        default_factory=list, description="List of house communication items"
    )
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class SenateCommunicationsResponse(BaseModel):
    """Wrapper for senate communications list responses."""

    senateCommunications: List["SenateCommunicationListItem"] = Field(
        default_factory=list, description="List of senate communication items"
    )
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)

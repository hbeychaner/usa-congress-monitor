"""Meta and response Pydantic models used by the ingest pipeline.

Small, focused models used to coerce chunk/meta payloads and parse
API responses for spec-driven consumers.
"""

from __future__ import annotations

from typing import Optional, List
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from src.models.other_models import CommitteeReportListItem
from src.models.other_models import (
    BillListItem,
    MemberListItem,
    CRSReport,
    CommitteeMeetingListItem,
    HearingListItem,
    AmendmentListItem,
    CommitteeListItem,
    NominationListItem,
    BillSummaryListItem,
    TreatyListItem,
    HouseRequirementListItem,
    CommitteePrintListItem,
    HouseCommunicationListItem,
    SenateCommunicationListItem,
)


class BaseChunkMeta(BaseModel):
    offset: int = Field(0, description="Offset for paginated endpoints")
    limit: int = Field(250, description="Limit/page size for paginated endpoints")
    model_config = ConfigDict(validate_by_name=True)


class GenericChunkMeta(BaseChunkMeta):
    congress: Optional[int] = Field(None, description="Congress number")
    type: Optional[str] = Field(None, description="Record type or bill type")
    chamber: Optional[str] = Field(None, description="Chamber filter (house/senate)")
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
    reports: List[CommitteeReportListItem] = Field(
        default_factory=list, description="List of committee report items"
    )
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class BillListResponse(BaseModel):
    bills: List[BillListItem] = Field(
        default_factory=list, description="List of bill items"
    )
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class MemberListResponse(BaseModel):
    members: List[MemberListItem] = Field(
        default_factory=list, description="List of member items"
    )
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class CRSReportsResponse(BaseModel):
    CRSReports: List[CRSReport] = Field(
        default_factory=list, description="List of CRS report items"
    )
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class CongressMeta(BaseChunkMeta):
    congress: Optional[int] = Field(None, description="Congress number")


class CongressListResponse(BaseModel):
    congresses: List[Any] = Field(default_factory=list, description="List of congress items")
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class CommitteeListResponse(BaseModel):
    committees: List[CommitteeListItem] = Field(default_factory=list, description="List of committee items")
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class NominationListResponse(BaseModel):
    nominations: List[NominationListItem] = Field(default_factory=list, description="List of nomination items")
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class BoundCongressionalRecordResponse(BaseModel):
    boundCongressionalRecord: List[Any] = Field(default_factory=list, description="List of bound congressional record items")
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class DailyCongressionalRecordResponse(BaseModel):
    dailyCongressionalRecord: List[Any] = Field(default_factory=list, description="List of daily congressional record items")
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class SummariesResponse(BaseModel):
    summaries: List[BillSummaryListItem] = Field(default_factory=list, description="List of summary items")
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class TreatyListResponse(BaseModel):
    treaties: List[TreatyListItem] = Field(default_factory=list, description="List of treaty items")
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class HouseRequirementsResponse(BaseModel):
    houseRequirements: List[HouseRequirementListItem] = Field(default_factory=list, description="List of house requirement items")
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class HouseVotesResponse(BaseModel):
    houseRollCallVotes: List[Any] = Field(default_factory=list, description="List of house roll call vote items")
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class CommitteeMeetingsResponse(BaseModel):
    committeeMeetings: List[CommitteeMeetingListItem] = Field(
        default_factory=list, description="List of committee meeting items"
    )
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class HearingsResponse(BaseModel):
    hearings: List[HearingListItem] = Field(
        default_factory=list, description="List of hearing items"
    )
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class AmendmentsResponse(BaseModel):
    amendments: List[AmendmentListItem] = Field(
        default_factory=list, description="List of amendment items"
    )
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class CommitteePrintsResponse(BaseModel):
    committeePrints: List["CommitteePrintListItem"] = Field(
        default_factory=list, description="List of committee print items"
    )
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class HouseCommunicationsResponse(BaseModel):
    houseCommunications: List["HouseCommunicationListItem"] = Field(
        default_factory=list, description="List of house communication items"
    )
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)


class SenateCommunicationsResponse(BaseModel):
    senateCommunications: List["SenateCommunicationListItem"] = Field(
        default_factory=list, description="List of senate communication items"
    )
    pagination: Optional[dict] = None
    model_config = ConfigDict(validate_by_name=True)

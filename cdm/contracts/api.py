from pydantic import BaseModel, Field


class StateSummary(BaseModel):
    code: str = Field(description="Two-letter state code")
    name: str = Field(description="State display name")


class TimelineMember(BaseModel):
    bioguide_id: str
    name: str
    party: str
    congress_start: int
    congress_end: int


class CongressGroup(BaseModel):
    congress: int
    members: list[TimelineMember]


class ChamberTimeline(BaseModel):
    chamber: str
    members: list[TimelineMember]
    groups: list[CongressGroup] = Field(default_factory=list)


class StateTimelineResponse(BaseModel):
    state_code: str
    state_name: str
    house: ChamberTimeline
    senate: ChamberTimeline


class MemberSummary(BaseModel):
    bioguide_id: str
    display_name: str
    party: str
    state: str
    chamber: str | None = None
    district: int | None = None
    term_start_year: int | None = None
    term_end_year: int | None = None
    image_url: str | None = None


class MembersResponse(BaseModel):
    members: list[MemberSummary]
    total: int
    page: int = 1
    limit: int = 50


class ActivityItem(BaseModel):
    bill_id: str
    title: str
    activity_type: str
    congress: int


class TopicItem(BaseModel):
    label: str
    weight: float


class MemberProfileResponse(BaseModel):
    member: MemberSummary
    recent_activity: list[ActivityItem]
    topics: list[TopicItem]


class SearchResultItem(BaseModel):
    id: str
    result_type: str
    title: str
    subtitle: str | None = None


class SearchResponse(BaseModel):
    query: str
    types: list[str]
    limit: int
    results: list[SearchResultItem]


class BillSummary(BaseModel):
    bill_id: str
    title: str
    congress: int | None = None
    bill_type: str | None = None
    number: str | None = None
    chamber: str | None = None
    updated_at: str | None = None


class BillsResponse(BaseModel):
    bills: list[BillSummary]
    total: int
    page: int = 1
    limit: int = 50


class BillDetail(BaseModel):
    bill_id: str
    title: str
    congress: int | None = None
    bill_type: str | None = None
    number: str | None = None
    origin_chamber: str | None = None
    origin_chamber_code: str | None = None
    introduced_date: str | None = None
    update_date: str | None = None
    update_date_including_text: str | None = None
    latest_action: dict | None = None
    policy_area: str | None = None
    sponsors: list[dict] = Field(default_factory=list)
    subjects: dict | None = None
    laws: list[dict] = Field(default_factory=list)
    constitutional_authority_statement_text: str | None = None
    full_text: str | None = None
    relationship_counts: dict[str, int] = Field(default_factory=dict)


class BillDetailResponse(BaseModel):
    bill: BillDetail


class IngestProgressJob(BaseModel):
    job_id: str
    status: str
    resource: str
    from_date: str | None = None
    to_date: str | None = None
    fetch_items: bool
    hydrated: int
    discovered: int
    target: int
    remaining: int


class IngestProgressResponse(BaseModel):
    hydrated: int
    discovered: int
    target: int
    remaining: int
    active_jobs: int
    jobs: list[IngestProgressJob]


class JobStatusCounts(BaseModel):
    queued: int = 0
    running: int = 0
    retrying: int = 0
    succeeded: int = 0
    failed: int = 0


class GovInfoCoverage(BaseModel):
    congress: int
    expected: int = 0
    available: int = 0
    pending: int = 0
    failed: int = 0
    not_available: int = 0
    complete: bool = False
    report_found: bool = False


class StagingStatus(BaseModel):
    index: str
    exists: bool = False
    documents: int = 0
    production_alias_target: str | None = None
    connected: bool = False


class AdminIngestSnapshot(BaseModel):
    congress: int
    govinfo: GovInfoCoverage
    govinfo_jobs: JobStatusCounts
    govinfo_batch_jobs: JobStatusCounts
    index_jobs: JobStatusCounts
    reconcile_jobs: JobStatusCounts
    staging: StagingStatus
    ready_for_reconciliation: bool
    ready_for_cutover: bool

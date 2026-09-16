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


class MemberTerm(BaseModel):
    chamber: str | None = None
    congress: int | None = None
    start_year: int | None = None
    end_year: int | None = None
    member_type: str | None = None
    state_code: str | None = None
    state_name: str | None = None
    district: int | None = None


class MemberDetail(MemberSummary):
    honorific_name: str | None = None
    birth_year: str | None = None
    death_year: str | None = None
    official_website_url: str | None = None
    office_address: str | None = None
    phone_number: str | None = None
    current_member: bool | None = None
    leadership: list[dict] = Field(default_factory=list)
    party_history: list[dict] = Field(default_factory=list)
    terms: list[MemberTerm] = Field(default_factory=list)
    image_attribution: str | None = None


class ActivityItem(BaseModel):
    bill_id: str
    title: str
    activity_type: str
    congress: int


class TopicItem(BaseModel):
    label: str
    weight: float


class MemberProfileResponse(BaseModel):
    member: MemberDetail
    recent_activity: list[ActivityItem]
    topics: list[TopicItem]


class MemberActivityItem(BaseModel):
    id: str
    document_type: str  # "bill" | "amendment" (extensible: "vote", ...)
    activity_type: str  # "Sponsor" | "Cosponsor"
    title: str
    date: str | None = None
    congress: int | None = None
    bill_id: str | None = None


class MemberActivityResponse(BaseModel):
    items: list[MemberActivityItem]
    total: int
    counts: dict[str, int]
    page: int = 1
    limit: int = 25


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
    cosponsors: list[dict] = Field(default_factory=list)
    actions: list[dict] = Field(default_factory=list)
    summaries: list[dict] = Field(default_factory=list)
    titles: list[dict] = Field(default_factory=list)
    text_versions: list[dict] = Field(default_factory=list)
    committees: list[dict] = Field(default_factory=list)
    related_bills: list[dict] = Field(default_factory=list)
    subjects: dict | None = None
    laws: list[dict] = Field(default_factory=list)
    constitutional_authority_statement_text: str | None = None
    full_text: str | None = None
    full_text_version_code: str | None = None
    relationship_counts: dict[str, int] = Field(default_factory=dict)


class BillDetailResponse(BaseModel):
    bill: BillDetail


class VotePartyTotals(BaseModel):
    yea: int = 0
    nay: int = 0
    present: int = 0
    not_voting: int = 0


class VoteSummary(BaseModel):
    vote_id: str
    congress: int | None = None
    session_number: int | None = None
    roll_call_number: int | None = None
    chamber: str = "House"
    vote_type: str | None = None
    result: str | None = None
    question: str | None = None
    date: str | None = None
    totals: VotePartyTotals
    amendment_number: int | None = None
    url: str | None = None


class BillVotesResponse(BaseModel):
    bill_id: str
    votes: list[VoteSummary]
    total: int


class IngestProgressJob(BaseModel):
    job_id: str
    status: str
    resource: str
    congress: int | None = None
    from_date: str | None = None
    to_date: str | None = None
    fetch_items: bool
    hydrated: int
    discovered: int
    target: int
    remaining: int


class BackfillProgress(BaseModel):
    total: int
    succeeded: int
    pending: int
    failed: int
    percent: float = Field(description="Completion percentage, 0-100.")
    rate_per_hour: int = Field(
        description="Packages completed in the trailing hour."
    )
    eta: str | None = Field(
        default=None,
        description="Estimated completion timestamp (UTC) from the trailing-hour rate.",
    )
    batches_pending: int = 0


class IngestProgressResponse(BaseModel):
    hydrated: int
    discovered: int
    target: int
    remaining: int
    active_jobs: int
    activity: str = Field(description="Overall ingest activity state.")
    last_progress_at: str | None = Field(
        default=None, description="Most recent durable ingest progress heartbeat."
    )
    jobs: list[IngestProgressJob]
    backfill: BackfillProgress | None = None


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


class IndexStatus(BaseModel):
    name: str
    documents: int = 0


class SystemStatusResponse(BaseModel):
    search_connected: bool = False
    indices: list[IndexStatus] = Field(default_factory=list)
    jobs: dict[str, JobStatusCounts] = Field(default_factory=dict)
    generated_at: str | None = None

from enum import StrEnum
from typing import Literal

from pydantic import Field, JsonValue

from cdm.contracts.analysis import AnalysisResponse, AnalysisState, AnalysisStatus
from cdm.contracts.base import ResponseModel
from cdm.contracts.hydration import HydrationAssessment
from cdm.contracts.labels import LabelProvenance
from cdm.contracts.queries import WindowedResponse
from cdm.graph.models import PartyGroup, Signal
from cdm.perspectives.models import SubjectUse, TermUse, TopicPerspectives


class HealthResponse(ResponseModel):
    status: str


class ReadinessResponse(ResponseModel):
    status: Literal["ready"]


class ErrorResponse(ResponseModel):
    detail: str


class AnalysisErrorResponse(ErrorResponse):
    analysis_state: Literal[AnalysisState.NOT_BUILT, AnalysisState.UNAVAILABLE]


class DistrictProperties(ResponseModel):
    state: str
    district: int


class DistrictFeature(ResponseModel):
    type: Literal["Feature"]
    id: str
    properties: DistrictProperties
    geometry: dict[str, JsonValue]


class DistrictFeatureCollection(ResponseModel):
    type: Literal["FeatureCollection"]
    features: list[DistrictFeature]


class StateSummary(ResponseModel):
    code: str = Field(description="Two-letter state code")
    name: str = Field(description="State display name")


class TimelineMember(ResponseModel):
    bioguide_id: str
    name: str
    party: str
    congress_start: int
    congress_end: int


class CongressGroup(ResponseModel):
    congress: int
    members: list[TimelineMember]


class ChamberTimeline(ResponseModel):
    chamber: str
    members: list[TimelineMember]
    groups: list[CongressGroup] = Field(default_factory=list)


class StateTimelineResponse(ResponseModel):
    state_code: str
    state_name: str
    house: ChamberTimeline
    senate: ChamberTimeline


class MemberSummary(ResponseModel):
    bioguide_id: str
    display_name: str
    party: str
    state: str
    chamber: str | None = None
    district: int | None = None
    term_start_year: int | None = None
    term_end_year: int | None = None
    image_url: str | None = None


class MembersResponse(WindowedResponse):
    members: list[MemberSummary]


class MemberTerm(ResponseModel):
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


class ActivityItem(ResponseModel):
    bill_id: str
    title: str
    activity_type: str
    congress: int


class TopicItem(ResponseModel):
    label: str
    weight: float
    topic_id: int | None = None


class TopicSummary(LabelProvenance):
    topic_id: int
    name: str
    label: str
    size: int
    top_words: list[str] = Field(default_factory=list)
    metasubject_id: int | None = None


class TopicsResponse(AnalysisResponse):
    topics: list[TopicSummary]
    model_version: str | None = None
    trained_at: str | None = None


class TopicTrendPoint(ResponseModel):
    timestamp: str
    frequency: int
    words: str | None = None


class TopicTrendSeries(ResponseModel):
    topic_id: int
    label: str
    points: list[TopicTrendPoint]


class TopicTrendsResponse(AnalysisResponse):
    series: list[TopicTrendSeries]
    model_version: str | None = None


class MetasubjectSummary(LabelProvenance):
    metasubject_id: int
    name: str
    size: int
    top_words: list[str] = Field(default_factory=list)
    topic_ids: list[int] = Field(default_factory=list)


class RelatedMetasubject(ResponseModel):
    metasubject_id: int
    name: str
    similarity: float


class MetasubjectsResponse(AnalysisResponse):
    metasubjects: list[MetasubjectSummary]
    model_version: str | None = None


class MetasubjectTrendSeries(ResponseModel):
    metasubject_id: int
    label: str
    points: list[TopicTrendPoint]


class MetasubjectTrendsResponse(AnalysisResponse):
    series: list[MetasubjectTrendSeries]
    model_version: str | None = None


class MetasubjectDetailResponse(AnalysisResponse):
    metasubject: MetasubjectSummary
    related: list[RelatedMetasubject] = Field(default_factory=list)
    topics: list[TopicSummary] = Field(default_factory=list)
    trend: list[TopicTrendPoint] = Field(default_factory=list)
    model_version: str | None = None


class TopicBill(ResponseModel):
    bill_id: str
    title: str | None = None
    probability: float


class RelatedTopic(ResponseModel):
    topic_id: int
    label: str
    similarity: float


class TopicDetailResponse(AnalysisResponse):
    topic: TopicSummary
    related: list[RelatedTopic] = Field(default_factory=list)
    model_version: str | None = None
    trend: list[TopicTrendPoint] = Field(default_factory=list)
    top_bills: list[TopicBill] = Field(default_factory=list)


class TopicAssignmentItem(ResponseModel):
    topic_id: int
    label: str
    probability: float


class BillTopicsResponse(AnalysisResponse):
    bill_id: str
    topics: list[TopicAssignmentItem] = Field(default_factory=list)
    model_version: str | None = None


class MemberTopicTrendPoint(ResponseModel):
    period: str
    topic_id: int
    label: str
    count: int


class MemberTopicsResponse(AnalysisResponse):
    bioguide_id: str
    topics: list[TopicItem] = Field(default_factory=list)
    trend: list[MemberTopicTrendPoint] = Field(default_factory=list)
    model_version: str | None = None
    subjects: list[TopicItem] = Field(default_factory=list)
    policy_areas: list[TopicItem] = Field(default_factory=list)


class TrainingState(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TopicTrainingStatus(ResponseModel):
    state: TrainingState = TrainingState.IDLE
    job_id: str | None = None
    started: bool | None = None
    pid: int | None = None
    stage: str | None = None
    progress: float | None = None
    message: str | None = None
    model_version: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    updated_at: str | None = None


class SubjectCount(ResponseModel):
    name: str
    count: int


class SubjectsResponse(ResponseModel):
    subjects: list[SubjectCount] = Field(default_factory=list)
    policy_areas: list[SubjectCount] = Field(default_factory=list)
    total_bills: int = 0


class PolicyAreaTrendPoint(ResponseModel):
    year: int
    count: int


class PolicyAreaTrendSeries(ResponseModel):
    name: str
    total: int
    points: list[PolicyAreaTrendPoint]


class PolicyAreaTrendsResponse(ResponseModel):
    series: list[PolicyAreaTrendSeries] = Field(default_factory=list)
    total_bills: int = 0


class MemberProfileResponse(ResponseModel):
    member: MemberDetail
    recent_activity: list[ActivityItem]


class MemberActivityItem(ResponseModel):
    id: str
    document_type: str  # "bill" | "amendment" (extensible: "vote", ...)
    activity_type: str  # "Sponsor" | "Cosponsor"
    title: str
    date: str | None = None
    congress: int | None = None
    bill_id: str | None = None


class MemberActivityResponse(WindowedResponse):
    items: list[MemberActivityItem]
    counts: dict[str, int]
    limit: int = 25


class SearchResultItem(ResponseModel):
    id: str
    result_type: str
    title: str
    subtitle: str | None = None


class SearchResponse(ResponseModel):
    query: str
    types: list[str]
    limit: int = Field(description="Maximum results per selected entity type.")
    ordering: Literal["grouped"] = "grouped"
    results: list[SearchResultItem]


class BillSummary(ResponseModel):
    bill_id: str
    title: str
    congress: int | None = None
    bill_type: str | None = None
    number: str | None = None
    chamber: str | None = None
    updated_at: str | None = None
    vote_count: int = 0


class BillsResponse(WindowedResponse):
    bills: list[BillSummary]


class SimilarBill(ResponseModel):
    bill_id: str
    title: str
    congress: int | None = None
    score: float


class CommitteeActivity(ResponseModel):
    name: str
    date: str | None = None


class CommitteeBill(ResponseModel):
    bill_id: str
    title: str
    congress: int | None = None
    chamber: str | None = None
    activities: list[CommitteeActivity] = Field(default_factory=list)


class CommitteeDetailResponse(ResponseModel):
    system_code: str
    name: str
    chamber: str | None = None
    committee_type: str | None = None
    total: int
    page: int = 1
    limit: int = 50
    bills: list[CommitteeBill] = Field(default_factory=list)


class SimilarBillsResponse(AnalysisResponse):
    bill_id: str
    similar: list[SimilarBill] = Field(default_factory=list)


class BillDetail(ResponseModel):
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
    hydration: HydrationAssessment = Field(default_factory=HydrationAssessment)


class BillDetailResponse(ResponseModel):
    bill: BillDetail


class VotePartyTotals(ResponseModel):
    yea: int = 0
    nay: int = 0
    present: int = 0
    not_voting: int = 0


class VoteSummary(ResponseModel):
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
    rollcall_id: str | None = None


class BillVotesResponse(ResponseModel):
    bill_id: str
    votes: list[VoteSummary]
    total: int


class VotePosition(StrEnum):
    YEA = "yea"
    NAY = "nay"
    PRESENT = "present"
    NOT_VOTING = "not_voting"


class VoteMember(ResponseModel):
    bioguide_id: str
    name: str
    state: str | None = None


class PositionMembers(ResponseModel):
    position: VotePosition
    members: list[VoteMember]


class PartyVoteBreakdown(ResponseModel):
    party: PartyGroup
    positions: list[PositionMembers]


class VoteBreakdownResponse(ResponseModel):
    vote_id: str
    parties: list[PartyVoteBreakdown]


class IngestProgressJob(ResponseModel):
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
    rate_per_hour: int = Field(
        default=0, description="Average items hydrated per hour since start."
    )
    eta: str | None = None


class BackfillProgress(ResponseModel):
    total: int
    succeeded: int
    pending: int
    failed: int
    percent: float = Field(description="Completion percentage, 0-100.")
    rate_per_hour: int = Field(description="Packages completed in the trailing hour.")
    eta: str | None = Field(
        default=None,
        description="Estimated completion timestamp (UTC) from the trailing-hour rate.",
    )
    batches_pending: int = 0


class IngestProgressResponse(ResponseModel):
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


class JobStatusCounts(ResponseModel):
    queued: int = 0
    running: int = 0
    retrying: int = 0
    succeeded: int = 0
    failed: int = 0


class GovInfoCoverage(ResponseModel):
    congress: int
    expected: int = 0
    available: int = 0
    pending: int = 0
    failed: int = 0
    not_available: int = 0
    complete: bool = False
    report_found: bool = False


class StagingStatus(ResponseModel):
    index: str
    exists: bool = False
    documents: int = 0
    production_alias_target: str | None = None
    connected: bool = False


class AdminIngestSnapshot(ResponseModel):
    congress: int
    govinfo: GovInfoCoverage
    govinfo_jobs: JobStatusCounts
    govinfo_batch_jobs: JobStatusCounts
    index_jobs: JobStatusCounts
    reconcile_jobs: JobStatusCounts
    staging: StagingStatus
    ready_for_reconciliation: bool
    ready_for_cutover: bool


class IndexStatus(ResponseModel):
    name: str
    documents: int = 0


class SystemStatusResponse(ResponseModel):
    search_connected: bool = False
    indices: list[IndexStatus] = Field(default_factory=list)
    jobs: dict[str, JobStatusCounts] = Field(default_factory=dict)
    generated_at: str | None = None


class SimilarMember(ResponseModel):
    member: MemberSummary
    score: float
    member_sponsored: int = 0
    neighbor_sponsored: int = 0
    co_signed: float = 0.0
    shared_votes: int = 0
    agreed_votes: int = 0
    shared_split_votes: int = 0
    agreed_split_votes: int = 0
    shared_topics: list[str] = Field(default_factory=list)


class SimilarMembersResponse(AnalysisResponse):
    member_id: str
    signal: Signal
    congress: int | None = None
    graph_version: str | None = None
    similar: list[SimilarMember]


class GraphNode(ResponseModel):
    member: MemberSummary
    party_group: PartyGroup
    is_seed: bool = False


class GraphLink(ResponseModel):
    source: str
    target: str
    score: float
    signal_scores: dict[Signal, float] = Field(default_factory=dict)
    shared_topics: list[str] = Field(default_factory=list)


class GraphTopicNode(ResponseModel):
    topic_id: int
    label: str


class GraphTopicLink(ResponseModel):
    member: str
    topic_id: int
    share: float
    bills: int


class GraphSubjectNode(ResponseModel):
    name: str


class GraphSubjectLink(ResponseModel):
    member: str
    subject: str
    bills: int


class GraphMetasubjectNode(ResponseModel):
    metasubject_id: int
    name: str


class GraphMetasubjectLink(ResponseModel):
    member: str
    metasubject_id: int
    share: float
    bills: int


class NeighborhoodResponse(ResponseModel):
    seeds: list[str]
    analysis: dict[Signal, AnalysisStatus]
    topic_analysis: AnalysisStatus | None = None
    congress: int | None = None
    versions: dict[Signal, str] = Field(default_factory=dict)
    nodes: list[GraphNode] = Field(default_factory=list)
    links: list[GraphLink] = Field(default_factory=list)
    topic_nodes: list[GraphTopicNode] = Field(default_factory=list)
    topic_links: list[GraphTopicLink] = Field(default_factory=list)
    subject_nodes: list[GraphSubjectNode] = Field(default_factory=list)
    subject_links: list[GraphSubjectLink] = Field(default_factory=list)
    metasubject_nodes: list[GraphMetasubjectNode] = Field(default_factory=list)
    metasubject_links: list[GraphMetasubjectLink] = Field(default_factory=list)


class PartyTopicEntry(ResponseModel):
    topic_id: int
    label: str
    bills: int
    topic_bills: int
    share_of_party: float
    share_of_topic: float
    summary: str = ""


class PartyRanking(ResponseModel):
    party: PartyGroup
    total_bills: int
    topics: list[PartyTopicEntry]


class BilateralTopicEntry(ResponseModel):
    topic_id: int
    label: str
    bills: int
    bipartisan_bills: int
    share: float
    terms: list[TermUse]
    subjects: list[SubjectUse]
    summary: str = ""


class PartiesResponse(AnalysisResponse):
    congress: int | None
    congresses: list[int]
    model_version: str | None
    parties: list[PartyRanking]
    bilateral: list[BilateralTopicEntry]


class PartyTopicResponse(AnalysisResponse):
    """One topic's party contrast; clusters appear only when they pass the stability gate."""

    topic: TopicPerspectives

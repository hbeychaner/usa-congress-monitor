# backend source reference

[All source areas](README.md)

Generated from declarations; see the catalogue scope in the index.

## cdm/backend/__init__.py

[Source](../../../cdm/backend/__init__.py)

No declarations in this module.


## cdm/backend/api/__init__.py

[Source](../../../cdm/backend/api/__init__.py)

No declarations in this module.


## cdm/backend/api/router.py

[Source](../../../cdm/backend/api/router.py)

No declarations in this module.


## cdm/backend/api/routes/__init__.py

[Source](../../../cdm/backend/api/routes/__init__.py)

No declarations in this module.


## cdm/backend/api/routes/admin.py

[Source](../../../cdm/backend/api/routes/admin.py)

- function: [`_start(jobs: AnalyticsJobs, request: AnalysisRequest, schema: type[Status]) -> Status`](../../../cdm/backend/api/routes/admin.py#L25)
- function: [`cancel_analytics(job_id: str, jobs: AnalyticsJobsDep) -> AnalysisSubmission`](../../../cdm/backend/api/routes/admin.py#L38)
- function: [`topic_training_status(jobs: AnalyticsJobsDep) -> TopicTrainingStatus`](../../../cdm/backend/api/routes/admin.py#L48)
- function: [`topic_training_start(jobs: AnalyticsJobsDep) -> TopicTrainingStatus`](../../../cdm/backend/api/routes/admin.py#L53)
- function: [`member_graph_status(jobs: AnalyticsJobsDep) -> GraphBuildStatus`](../../../cdm/backend/api/routes/admin.py#L58)
- function: [`member_graph_build(jobs: AnalyticsJobsDep) -> GraphBuildStatus`](../../../cdm/backend/api/routes/admin.py#L63)
- function: [`perspectives_status(jobs: AnalyticsJobsDep) -> GraphBuildStatus`](../../../cdm/backend/api/routes/admin.py#L68)
- function: [`perspectives_build(jobs: AnalyticsJobsDep) -> GraphBuildStatus`](../../../cdm/backend/api/routes/admin.py#L73)
- function: [`ingest_progress(service: AdminServiceDep) -> IngestProgressResponse`](../../../cdm/backend/api/routes/admin.py#L78)
- function: [`ingest_snapshot(service: AdminServiceDep) -> AdminIngestSnapshot`](../../../cdm/backend/api/routes/admin.py#L83)
- function: [`system_status(service: AdminServiceDep) -> SystemStatusResponse`](../../../cdm/backend/api/routes/admin.py#L88)

## cdm/backend/api/routes/bills.py

[Source](../../../cdm/backend/api/routes/bills.py)

- function: [`recent_bills(service: BillServiceDep, limit: int=Query(default=50, ge=10, le=100), page: int=Query(default=1, ge=1), query: str \| None=Query(default=None, max_length=200), congress: int \| None=Query(default=None, ge=1, le=200), bill_type: str \| None=Query(default=None, max_length=20), chamber: str \| None=Query(default=None, pattern='^(House\|Senate)$'), subject: str \| None=Query(default=None, max_length=200), has_votes: bool=Query(default=False)) -> BillsResponse`](../../../cdm/backend/api/routes/bills.py#L22)
- function: [`bill_detail(bill_id: str, service: BillServiceDep) -> BillDetailResponse`](../../../cdm/backend/api/routes/bills.py#L43)
- function: [`bill_votes(bill_id: str, service: VoteServiceDep) -> BillVotesResponse`](../../../cdm/backend/api/routes/bills.py#L48)
- function: [`bill_topics(bill_id: str, service: TopicServiceDep) -> BillTopicsResponse`](../../../cdm/backend/api/routes/bills.py#L53)
- function: [`similar_bills(bill_id: str, service: SimilarBillServiceDep, limit: int=Query(default=10, ge=1, le=50)) -> SimilarBillsResponse`](../../../cdm/backend/api/routes/bills.py#L58)

## cdm/backend/api/routes/committees.py

[Source](../../../cdm/backend/api/routes/committees.py)

- function: [`committee_detail(system_code: str, service: CommitteeServiceDep, limit: int=Query(default=50, ge=10, le=100), page: int=Query(default=1, ge=1)) -> CommitteeDetailResponse`](../../../cdm/backend/api/routes/committees.py#L10)

## cdm/backend/api/routes/graph.py

[Source](../../../cdm/backend/api/routes/graph.py)

- function: [`neighborhood(service: NeighborhoodServiceDep, member: Annotated[list[str], Query(min_length=1, max_length=5)], collaboration_weight: float=Query(default=1.0, ge=0, le=1), voting_weight: float=Query(default=0.6, ge=0, le=1), topic_weight: float=Query(default=0.3, ge=0, le=1), congress: int \| None=Query(default=None, ge=1), limit: int=Query(default=15, ge=1, le=50), party: Annotated[list[PartyGroup] \| None, Query()]=None, chamber: Chamber \| None=None, include_topics: bool=False, topics_per_member: int=Query(default=3, ge=1, le=8), include_subjects: bool=False, subjects_per_member: int=Query(default=3, ge=1, le=8), include_metasubjects: bool=False, metasubjects_per_member: int=Query(default=3, ge=1, le=8)) -> NeighborhoodResponse`](../../../cdm/backend/api/routes/graph.py#L17)
- function: [`topic_neighborhood(service: TopicNeighborhoodServiceDep, kind: CenterKind, key: str, collaboration_weight: float=Query(default=1.0, ge=0, le=1), voting_weight: float=Query(default=0.6, ge=0, le=1), topic_weight: float=Query(default=0.3, ge=0, le=1), congress: int \| None=Query(default=None, ge=1), limit: int=Query(default=15, ge=1, le=50), party: Annotated[list[PartyGroup] \| None, Query()]=None, chamber: Chamber \| None=None) -> NeighborhoodResponse`](../../../cdm/backend/api/routes/graph.py#L57)

## cdm/backend/api/routes/members.py

[Source](../../../cdm/backend/api/routes/members.py)

- function: [`get_members(service: MemberServiceDep, query: str \| None=Query(default=None, max_length=200), state: str \| None=Query(default=None, max_length=200), chamber: str \| None=Query(default=None, max_length=200), party: str \| None=Query(default=None, max_length=200), page: int=Query(default=1, ge=1), limit: int=Query(default=50, ge=10, le=100)) -> MembersResponse`](../../../cdm/backend/api/routes/members.py#L24)
- function: [`get_member(bioguide_id: str, service: MemberServiceDep) -> MemberProfileResponse`](../../../cdm/backend/api/routes/members.py#L41)
- function: [`get_member_activity(bioguide_id: str, service: MemberServiceDep, types: str \| None=Query(default=None, max_length=200, description='Comma-separated document types: bill,amendment'), page: int=Query(default=1, ge=1), limit: int=Query(default=25, ge=5, le=100)) -> MemberActivityResponse`](../../../cdm/backend/api/routes/members.py#L46)
- function: [`member_topics(bioguide_id: str, service: TopicServiceDep) -> MemberTopicsResponse`](../../../cdm/backend/api/routes/members.py#L61)
- function: [`similar_members(bioguide_id: str, graph: GraphServiceDep, signal: Annotated[Signal, Query()]=Signal.COLLABORATION, congress: int \| None=Query(default=None, ge=1), limit: int=Query(default=10, ge=1, le=50)) -> SimilarMembersResponse`](../../../cdm/backend/api/routes/members.py#L66)

## cdm/backend/api/routes/parties.py

[Source](../../../cdm/backend/api/routes/parties.py)

- function: [`parties(service: PartyServiceDep, congress: int \| None=None) -> PartiesResponse`](../../../cdm/backend/api/routes/parties.py#L10)
- function: [`party_topic(topic_id: int, congress: int, service: PartyServiceDep) -> PartyTopicResponse`](../../../cdm/backend/api/routes/parties.py#L15)

## cdm/backend/api/routes/search.py

[Source](../../../cdm/backend/api/routes/search.py)

- function: [`search(service: SearchServiceDep, q: str=Query(min_length=1, max_length=200), types: str=Query(default='member,state,bill', max_length=200), limit: int=Query(default=20, ge=1, le=100, description='Maximum results per selected type; groups are not globally ranked.')) -> SearchResponse`](../../../cdm/backend/api/routes/search.py#L10)

## cdm/backend/api/routes/states.py

[Source](../../../cdm/backend/api/routes/states.py)

- function: [`get_states(service: StateServiceDep) -> list[StateSummary]`](../../../cdm/backend/api/routes/states.py#L14)
- function: [`get_timeline(state_code: str, service: StateServiceDep, from_congress: int \| None=Query(default=None), to_congress: int \| None=Query(default=None)) -> StateTimelineResponse`](../../../cdm/backend/api/routes/states.py#L19)
- function: [`get_districts(state_code: str, service: StateServiceDep) -> DistrictFeatureCollection`](../../../cdm/backend/api/routes/states.py#L29)

## cdm/backend/api/routes/subjects.py

[Source](../../../cdm/backend/api/routes/subjects.py)

- function: [`subjects_list(service: SubjectServiceDep, congress: int \| None=Query(default=None, ge=1, le=200), size: int=Query(default=100, ge=10, le=500)) -> SubjectsResponse`](../../../cdm/backend/api/routes/subjects.py#L10)
- function: [`policy_area_trends(service: SubjectServiceDep, size: int=Query(default=10, ge=1, le=32), start_year: int \| None=Query(default=None, ge=1900, le=2100)) -> PolicyAreaTrendsResponse`](../../../cdm/backend/api/routes/subjects.py#L19)

## cdm/backend/api/routes/topics.py

[Source](../../../cdm/backend/api/routes/topics.py)

- function: [`topics_list(service: TopicServiceDep) -> TopicsResponse`](../../../cdm/backend/api/routes/topics.py#L17)
- function: [`topic_trends(service: TopicServiceDep, size: int=8) -> TopicTrendsResponse`](../../../cdm/backend/api/routes/topics.py#L22)
- function: [`metasubjects_list(service: TopicServiceDep) -> MetasubjectsResponse`](../../../cdm/backend/api/routes/topics.py#L27)
- function: [`metasubject_trends(service: TopicServiceDep) -> MetasubjectTrendsResponse`](../../../cdm/backend/api/routes/topics.py#L32)
- function: [`metasubject_detail(metasubject_id: int, service: TopicServiceDep) -> MetasubjectDetailResponse`](../../../cdm/backend/api/routes/topics.py#L37)
- function: [`topic_detail(topic_id: int, service: TopicServiceDep, bills: int=20) -> TopicDetailResponse`](../../../cdm/backend/api/routes/topics.py#L47)

## cdm/backend/api/routes/votes.py

[Source](../../../cdm/backend/api/routes/votes.py)

- function: [`vote_breakdown(vote_id: str, service: VoteBreakdownServiceDep) -> VoteBreakdownResponse`](../../../cdm/backend/api/routes/votes.py#L10)

## cdm/backend/app.py

[Source](../../../cdm/backend/app.py)

- function: [`health() -> HealthResponse`](../../../cdm/backend/app.py#L53)
- function: [`readiness(container: ContainerDep) -> ReadinessResponse`](../../../cdm/backend/app.py#L58)

## cdm/backend/dependencies.py

[Source](../../../cdm/backend/dependencies.py)

- function: [`get_container() -> Container`](../../../cdm/backend/dependencies.py#L31)
- function: [`get_analytics_jobs(container: ContainerDep) -> AnalyticsJobs`](../../../cdm/backend/dependencies.py#L38)
- function: [`get_similar_bill_service(container: ContainerDep) -> SimilarBillService`](../../../cdm/backend/dependencies.py#L45)
- function: [`get_committee_service(container: ContainerDep) -> CommitteeService`](../../../cdm/backend/dependencies.py#L49)
- function: [`get_bill_service(container: ContainerDep) -> BillService`](../../../cdm/backend/dependencies.py#L53)
- function: [`get_vote_service(container: ContainerDep) -> VoteService`](../../../cdm/backend/dependencies.py#L57)
- function: [`get_vote_breakdown_service(container: ContainerDep) -> VoteBreakdownService`](../../../cdm/backend/dependencies.py#L61)
- function: [`get_state_service(container: ContainerDep) -> StateService`](../../../cdm/backend/dependencies.py#L65)
- function: [`get_search_service(container: ContainerDep) -> SearchService`](../../../cdm/backend/dependencies.py#L69)
- function: [`get_subject_service(container: ContainerDep) -> SubjectService`](../../../cdm/backend/dependencies.py#L73)
- function: [`get_admin_service(container: ContainerDep) -> AdminService`](../../../cdm/backend/dependencies.py#L77)
- function: [`get_topic_service(container: ContainerDep) -> TopicService`](../../../cdm/backend/dependencies.py#L81)
- function: [`get_member_service(container: ContainerDep) -> MemberService`](../../../cdm/backend/dependencies.py#L85)
- function: [`get_graph_service(container: ContainerDep) -> GraphService`](../../../cdm/backend/dependencies.py#L89)
- function: [`get_neighborhood_service(container: ContainerDep) -> NeighborhoodService`](../../../cdm/backend/dependencies.py#L93)
- function: [`get_topic_neighborhood_service(container: ContainerDep) -> TopicNeighborhoodService`](../../../cdm/backend/dependencies.py#L97)
- function: [`get_party_service(container: ContainerDep) -> PartyService`](../../../cdm/backend/dependencies.py#L101)

## cdm/backend/errors.py

[Source](../../../cdm/backend/errors.py)

- class: [`EntityNotFoundError(ValueError)`](../../../cdm/backend/errors.py#L17)
- class: [`AnalysisNotBuiltError(RuntimeError)`](../../../cdm/backend/errors.py#L21)
- class: [`APIErrorHandlers()`](../../../cdm/backend/errors.py#L25)
- async function: [`APIErrorHandlers.invalid_query(request: Request, exc: Exception) -> JSONResponse`](../../../cdm/backend/errors.py#L27)
- async function: [`APIErrorHandlers.missing(_request: Request, exc: Exception) -> JSONResponse`](../../../cdm/backend/errors.py#L44)
- async function: [`APIErrorHandlers.not_built(_request: Request, exc: Exception) -> JSONResponse`](../../../cdm/backend/errors.py#L53)
- async function: [`APIErrorHandlers.unavailable(_request: Request, exc: Exception) -> JSONResponse`](../../../cdm/backend/errors.py#L62)

## cdm/backend/services/__init__.py

[Source](../../../cdm/backend/services/__init__.py)

No declarations in this module.


## cdm/backend/services/admin_service.py

[Source](../../../cdm/backend/services/admin_service.py)

- class: [`_ActiveJob()`](../../../cdm/backend/services/admin_service.py#L67)
- field: [`_ActiveJob.job_id: str`](../../../cdm/backend/services/admin_service.py#L68)
- field: [`_ActiveJob.status: str`](../../../cdm/backend/services/admin_service.py#L69)
- field: [`_ActiveJob.resource: str`](../../../cdm/backend/services/admin_service.py#L70)
- field: [`_ActiveJob.congress: int \| None`](../../../cdm/backend/services/admin_service.py#L71)
- field: [`_ActiveJob.outdir: Path`](../../../cdm/backend/services/admin_service.py#L72)
- field: [`_ActiveJob.from_date: str \| None`](../../../cdm/backend/services/admin_service.py#L73)
- field: [`_ActiveJob.to_date: str \| None`](../../../cdm/backend/services/admin_service.py#L74)
- field: [`_ActiveJob.fetch_items: bool`](../../../cdm/backend/services/admin_service.py#L75)
- field: [`_ActiveJob.refresh_stale: bool`](../../../cdm/backend/services/admin_service.py#L76)
- field: [`_ActiveJob.started_at: datetime \| None`](../../../cdm/backend/services/admin_service.py#L77)
- function: [`_parse_timestamp(value: str \| None) -> datetime \| None`](../../../cdm/backend/services/admin_service.py#L80)
- function: [`_rate_and_eta(job: _ActiveJob, hydrated: int, remaining: int) -> tuple[int, str \| None]`](../../../cdm/backend/services/admin_service.py#L90)
- function: [`_load_active_ingest_jobs(conn: Connection) -> list[_ActiveJob]`](../../../cdm/backend/services/admin_service.py#L105)
- field: [`_load_active_ingest_jobs.jobs: list[_ActiveJob]`](../../../cdm/backend/services/admin_service.py#L126)
- function: [`_count_rows(db_path: Path, statement) -> int`](../../../cdm/backend/services/admin_service.py#L155)
- function: [`_hydrated_count(job: _ActiveJob) -> int`](../../../cdm/backend/services/admin_service.py#L164)
- function: [`_cached_list_count(job: _ActiveJob) -> int`](../../../cdm/backend/services/admin_service.py#L174)
- function: [`_latest_progress_at(conn: Connection, job: _ActiveJob) -> str \| None`](../../../cdm/backend/services/admin_service.py#L179)
- function: [`_refresh_counts(conn: Connection, job: _ActiveJob) -> tuple[int, int] \| None`](../../../cdm/backend/services/admin_service.py#L188)
- function: [`_job_activity(status: str, last_progress_at: str \| None) -> str`](../../../cdm/backend/services/admin_service.py#L206)
- function: [`_backfill_progress(conn: Connection) -> BackfillProgress \| None`](../../../cdm/backend/services/admin_service.py#L223)
- field: [`_backfill_progress.eta: str \| None`](../../../cdm/backend/services/admin_service.py#L256)
- function: [`_job_status_counts(conn: Connection, kind: str) -> JobStatusCounts`](../../../cdm/backend/services/admin_service.py#L271)
- function: [`_govinfo_coverage(conn: Connection) -> GovInfoCoverage`](../../../cdm/backend/services/admin_service.py#L284)
- class: [`AdminService()`](../../../cdm/backend/services/admin_service.py#L318)
- function: [`AdminService.__init__(self, client: Elasticsearch, config: AppConfig, engine: Engine) -> None`](../../../cdm/backend/services/admin_service.py#L321)
- function: [`AdminService.get_ingest_progress(self) -> IngestProgressResponse`](../../../cdm/backend/services/admin_service.py#L328)
- field: [`AdminService.get_ingest_progress.jobs: list[IngestProgressJob]`](../../../cdm/backend/services/admin_service.py#L333)
- field: [`AdminService.get_ingest_progress.job_activities: list[str]`](../../../cdm/backend/services/admin_service.py#L337)
- field: [`AdminService.get_ingest_progress.latest_progress_at: str \| None`](../../../cdm/backend/services/admin_service.py#L338)
- function: [`AdminService._staging_status(self) -> StagingStatus`](../../../cdm/backend/services/admin_service.py#L414)
- function: [`AdminService.get_admin_ingest_snapshot(self) -> AdminIngestSnapshot`](../../../cdm/backend/services/admin_service.py#L427)
- function: [`AdminService.get_system_status(self) -> SystemStatusResponse`](../../../cdm/backend/services/admin_service.py#L452)
- field: [`AdminService.get_system_status.indices: list[IndexStatus]`](../../../cdm/backend/services/admin_service.py#L462)

## cdm/backend/services/bill_service.py

[Source](../../../cdm/backend/services/bill_service.py)

- class: [`BillService()`](../../../cdm/backend/services/bill_service.py#L22)
- function: [`BillService.__init__(self, client: Elasticsearch, vote_index: BillVoteIndex, reads: QueryReadConfig \| None=None) -> None`](../../../cdm/backend/services/bill_service.py#L25)
- function: [`BillService.list_recent(self, limit: int=50, page: int=1, query: str \| None=None, congress: int \| None=None, bill_type: str \| None=None, chamber: str \| None=None, subject: str \| None=None, has_votes: bool=False) -> BillsResponse`](../../../cdm/backend/services/bill_service.py#L35)
- field: [`BillService.list_recent.filters: list[dict[str, Any]]`](../../../cdm/backend/services/bill_service.py#L50)
- field: [`BillService.list_recent.search_query: dict[str, Any]`](../../../cdm/backend/services/bill_service.py#L61)
- function: [`BillService.get(self, bill_id: str) -> BillDetailResponse`](../../../cdm/backend/services/bill_service.py#L100)
- function: [`BillService._subject_filter(subject: str) -> dict[str, Any]`](../../../cdm/backend/services/bill_service.py#L158)
- function: [`BillService._text_query(text: str) -> dict[str, Any]`](../../../cdm/backend/services/bill_service.py#L177)
- field: [`BillService._text_query.should: list[dict[str, Any]]`](../../../cdm/backend/services/bill_service.py#L181)
- function: [`BillService._summary(hit: dict[str, Any]) -> BillSummary \| None`](../../../cdm/backend/services/bill_service.py#L202)
- field: [`BillService._summary.source: dict[str, Any]`](../../../cdm/backend/services/bill_service.py#L203)
- function: [`BillService._relationship_counts(self, source: dict[str, Any]) -> dict[str, int]`](../../../cdm/backend/services/bill_service.py#L217)
- field: [`BillService._relationship_counts.counts: dict[str, int]`](../../../cdm/backend/services/bill_service.py#L218)
- function: [`BillService._dict_list(source: dict[str, Any], field: str) -> list[dict[str, Any]]`](../../../cdm/backend/services/bill_service.py#L228)

## cdm/backend/services/bill_vote_index.py

[Source](../../../cdm/backend/services/bill_vote_index.py)

- class: [`LegislationType(StrEnum)`](../../../cdm/backend/services/bill_vote_index.py#L17)
- class: [`BillKey(BaseModel)`](../../../cdm/backend/services/bill_vote_index.py#L28)
- field: [`BillKey.congress: int`](../../../cdm/backend/services/bill_vote_index.py#L33)
- field: [`BillKey.legislation_type: LegislationType`](../../../cdm/backend/services/bill_vote_index.py#L34)
- field: [`BillKey.number: int`](../../../cdm/backend/services/bill_vote_index.py#L35)
- function: [`BillKey.parse(cls, bill_id: str) -> BillKey \| None`](../../../cdm/backend/services/bill_vote_index.py#L38)
- function: [`BillKey.bill_id(self) -> str`](../../../cdm/backend/services/bill_vote_index.py#L56)
- function: [`BillKey.house_vote_filter(self) -> JsonObject`](../../../cdm/backend/services/bill_vote_index.py#L62)
- class: [`VoteSource(StrEnum)`](../../../cdm/backend/services/bill_vote_index.py#L74)
- class: [`VoteBucket(BaseModel)`](../../../cdm/backend/services/bill_vote_index.py#L79)
- field: [`VoteBucket.key: str \| tuple[int, str, int \| str]`](../../../cdm/backend/services/bill_vote_index.py#L80)
- field: [`VoteBucket.doc_count: int`](../../../cdm/backend/services/bill_vote_index.py#L81)
- function: [`VoteBucket.bill_id(self) -> str \| None`](../../../cdm/backend/services/bill_vote_index.py#L84)
- class: [`VoteBuckets(BaseModel)`](../../../cdm/backend/services/bill_vote_index.py#L94)
- field: [`VoteBuckets.buckets: list[VoteBucket]`](../../../cdm/backend/services/bill_vote_index.py#L95)
- field: [`VoteBuckets.sum_other_doc_count: int`](../../../cdm/backend/services/bill_vote_index.py#L96)
- field: [`VoteBuckets.doc_count_error_upper_bound: int`](../../../cdm/backend/services/bill_vote_index.py#L97)
- class: [`BillVoteIndex()`](../../../cdm/backend/services/bill_vote_index.py#L100)
- function: [`BillVoteIndex.__init__(self, client: Elasticsearch, reads: QueryReadConfig \| None=None) -> None`](../../../cdm/backend/services/bill_vote_index.py#L103)
- function: [`BillVoteIndex._buckets(self, source: VoteSource, query: JsonObject, size: int) -> list[VoteBucket]`](../../../cdm/backend/services/bill_vote_index.py#L109)
- field: [`BillVoteIndex._buckets.aggregation: JsonObject`](../../../cdm/backend/services/bill_vote_index.py#L112)
- function: [`BillVoteIndex.bill_ids(self, congress: int \| None=None) -> list[str]`](../../../cdm/backend/services/bill_vote_index.py#L150)
- field: [`BillVoteIndex.bill_ids.congress_filter: list[JsonObject]`](../../../cdm/backend/services/bill_vote_index.py#L152)
- field: [`BillVoteIndex.bill_ids.ids: set[str]`](../../../cdm/backend/services/bill_vote_index.py#L155)
- function: [`BillVoteIndex.counts(self, bill_ids: list[str]) -> dict[str, int]`](../../../cdm/backend/services/bill_vote_index.py#L171)
- field: [`BillVoteIndex.counts.counts: dict[str, int]`](../../../cdm/backend/services/bill_vote_index.py#L177)
- field: [`BillVoteIndex.counts.query: JsonObject`](../../../cdm/backend/services/bill_vote_index.py#L179)

## cdm/backend/services/committee_service.py

[Source](../../../cdm/backend/services/committee_service.py)

- class: [`CommitteeService()`](../../../cdm/backend/services/committee_service.py#L17)
- function: [`CommitteeService.__init__(self, client: Elasticsearch) -> None`](../../../cdm/backend/services/committee_service.py#L18)
- function: [`CommitteeService.detail(self, system_code: str, page: int, limit: int) -> CommitteeDetailResponse`](../../../cdm/backend/services/committee_service.py#L21)
- field: [`CommitteeService.detail.chamber: str \| None`](../../../cdm/backend/services/committee_service.py#L50)
- field: [`CommitteeService.detail.committee_type: str \| None`](../../../cdm/backend/services/committee_service.py#L51)
- field: [`CommitteeService.detail.bills: list[CommitteeBill]`](../../../cdm/backend/services/committee_service.py#L52)
- field: [`CommitteeService.detail.source: dict[str, Any]`](../../../cdm/backend/services/committee_service.py#L54)
- function: [`CommitteeService._entry(self, committees: list[dict[str, Any]], system_code: str) -> dict[str, Any] \| None`](../../../cdm/backend/services/committee_service.py#L90)

## cdm/backend/services/graph_service.py

[Source](../../../cdm/backend/services/graph_service.py)

- class: [`GraphReadSnapshot(BaseModel)`](../../../cdm/backend/services/graph_service.py#L25)
- field: [`GraphReadSnapshot.pointers: dict[Signal, GraphVersionPointer \| None]`](../../../cdm/backend/services/graph_service.py#L26)
- field: [`GraphReadSnapshot.topic_model_version: str \| None`](../../../cdm/backend/services/graph_service.py#L27)
- function: [`GraphReadSnapshot.versions(self) -> dict[Signal, str]`](../../../cdm/backend/services/graph_service.py#L30)
- function: [`GraphReadSnapshot.analysis(self, with_results: set[Signal], congress: int \| None=None) -> dict[Signal, AnalysisStatus]`](../../../cdm/backend/services/graph_service.py#L37)
- field: [`GraphReadSnapshot.analysis.statuses: dict[Signal, AnalysisStatus]`](../../../cdm/backend/services/graph_service.py#L40)
- class: [`GraphService()`](../../../cdm/backend/services/graph_service.py#L78)
- function: [`GraphService.__init__(self, store: GraphStore, members: MemberService, publications: TopicPublicationStore, reads: QueryReadConfig \| None=None) -> None`](../../../cdm/backend/services/graph_service.py#L81)
- function: [`GraphService.snapshot(self, signals: list[Signal], *, include_topics: bool=False) -> GraphReadSnapshot`](../../../cdm/backend/services/graph_service.py#L94)
- function: [`GraphService.edges(self, version: str, signal: Signal, members: list[str], congress: int \| None, size: int, neighbors: list[str] \| None=None) -> list[MemberEdge]`](../../../cdm/backend/services/graph_service.py#L107)
- field: [`GraphService.edges.filters: list[JsonObject]`](../../../cdm/backend/services/graph_service.py#L117)
- field: [`GraphService.edges.sort: JsonObject`](../../../cdm/backend/services/graph_service.py#L126)
- field: [`GraphService.edges.congress_filter: JsonObject`](../../../cdm/backend/services/graph_service.py#L128)
- function: [`GraphService.score(edge: MemberEdge, congress: int \| None) -> float`](../../../cdm/backend/services/graph_service.py#L157)
- function: [`GraphService.similar(self, bioguide_id: str, signal: Signal, congress: int \| None, limit: int) -> SimilarMembersResponse`](../../../cdm/backend/services/graph_service.py#L165)
- function: [`GraphService._similar_member(self, member: MemberSummary, edge: MemberEdge, congress: int \| None) -> SimilarMember`](../../../cdm/backend/services/graph_service.py#L196)
- field: [`GraphService._similar_member.selected: list[CongressEdgeStats]`](../../../cdm/backend/services/graph_service.py#L199)

## cdm/backend/services/member_metasubject_overlay.py

[Source](../../../cdm/backend/services/member_metasubject_overlay.py)

- class: [`MetasubjectOverlay()`](../../../cdm/backend/services/member_metasubject_overlay.py#L13)
- function: [`MetasubjectOverlay.__init__(self, nodes: list[GraphMetasubjectNode], links: list[GraphMetasubjectLink]) -> None`](../../../cdm/backend/services/member_metasubject_overlay.py#L14)
- class: [`MemberMetasubjectOverlayBuilder()`](../../../cdm/backend/services/member_metasubject_overlay.py#L21)
- function: [`MemberMetasubjectOverlayBuilder.__init__(self, bills: SponsoredBillReader, topics: TopicService) -> None`](../../../cdm/backend/services/member_metasubject_overlay.py#L22)
- function: [`MemberMetasubjectOverlayBuilder.build(self, member_ids: list[str], congress: int \| None, per_member: int, version: str \| None) -> MetasubjectOverlay`](../../../cdm/backend/services/member_metasubject_overlay.py#L26)
- field: [`MemberMetasubjectOverlayBuilder.build.links: list[GraphMetasubjectLink]`](../../../cdm/backend/services/member_metasubject_overlay.py#L38)

## cdm/backend/services/member_service.py

[Source](../../../cdm/backend/services/member_service.py)

- function: [`_terms(source: dict[str, Any]) -> list[dict[str, Any]]`](../../../cdm/backend/services/member_service.py#L25)
- function: [`_congress_for_year(year: int) -> int`](../../../cdm/backend/services/member_service.py#L32)
- function: [`_expand_terms(source: dict[str, Any]) -> list[MemberTerm]`](../../../cdm/backend/services/member_service.py#L36)
- field: [`_expand_terms.rows: list[MemberTerm]`](../../../cdm/backend/services/member_service.py#L40)
- function: [`_current_term(source: dict[str, Any]) -> dict[str, Any]`](../../../cdm/backend/services/member_service.py#L78)
- function: [`_member_summary(source: dict[str, Any], fallback_id: str='') -> MemberSummary`](../../../cdm/backend/services/member_service.py#L91)
- function: [`_member_detail(source: dict[str, Any], fallback_id: str='') -> MemberDetail`](../../../cdm/backend/services/member_service.py#L111)
- function: [`_member_link_query(bioguide_id: str, extra_filters: list[dict[str, Any]]) -> dict[str, Any]`](../../../cdm/backend/services/member_service.py#L137)
- function: [`_activity_type(source: dict[str, Any], bioguide_id: str) -> str`](../../../cdm/backend/services/member_service.py#L158)
- function: [`_bill_activity_item(source: dict[str, Any], bioguide_id: str) -> MemberActivityItem`](../../../cdm/backend/services/member_service.py#L166)
- function: [`_amendment_activity_item(source: dict[str, Any], bioguide_id: str) -> MemberActivityItem`](../../../cdm/backend/services/member_service.py#L179)
- class: [`ActivityCount(BaseModel)`](../../../cdm/backend/services/member_service.py#L200)
- field: [`ActivityCount.doc_count: int`](../../../cdm/backend/services/member_service.py#L201)
- class: [`ActivityTotals(BaseModel)`](../../../cdm/backend/services/member_service.py#L204)
- field: [`ActivityTotals.counts: dict[ActivityKind, ActivityCount]`](../../../cdm/backend/services/member_service.py#L205)
- class: [`MemberService()`](../../../cdm/backend/services/member_service.py#L210)
- function: [`MemberService.__init__(self, client: Elasticsearch, search: SearchService, reads: QueryReadConfig \| None=None) -> None`](../../../cdm/backend/services/member_service.py#L211)
- function: [`MemberService.list_members(self, query: str \| None, state: str \| None, chamber: str \| None, party: str \| None, page: int, limit: int) -> MembersResponse`](../../../cdm/backend/services/member_service.py#L221)
- field: [`MemberService.list_members.filters: list[dict[str, Any]]`](../../../cdm/backend/services/member_service.py#L239)
- field: [`MemberService.list_members.query_body: dict[str, Any]`](../../../cdm/backend/services/member_service.py#L250)
- field: [`MemberService.list_members.text_should: list[dict[str, Any]]`](../../../cdm/backend/services/member_service.py#L252)
- function: [`MemberService.get_profile(self, bioguide_id: str) -> MemberProfileResponse`](../../../cdm/backend/services/member_service.py#L298)
- function: [`MemberService.list_activity(self, bioguide_id: str, types: str \| None=None, page: int=1, limit: int=25) -> MemberActivityResponse`](../../../cdm/backend/services/member_service.py#L336)
- field: [`MemberService.list_activity.items: list[MemberActivityItem]`](../../../cdm/backend/services/member_service.py#L398)
- function: [`MemberService.get_summaries(self, bioguide_ids: list[str]) -> dict[str, MemberSummary]`](../../../cdm/backend/services/member_service.py#L422)
- field: [`MemberService.get_summaries.summaries: dict[str, MemberSummary]`](../../../cdm/backend/services/member_service.py#L430)
- function: [`MemberService._richness(hit: dict[str, Any]) -> int`](../../../cdm/backend/services/member_service.py#L438)
- function: [`MemberService._recent_activity(self, bioguide_id: str, limit: int=20) -> list[ActivityItem]`](../../../cdm/backend/services/member_service.py#L452)
- field: [`MemberService._recent_activity.activity: list[ActivityItem]`](../../../cdm/backend/services/member_service.py#L471)

## cdm/backend/services/member_subject_overlay.py

[Source](../../../cdm/backend/services/member_subject_overlay.py)

- class: [`SubjectBucket(BaseModel)`](../../../cdm/backend/services/member_subject_overlay.py#L20)
- field: [`SubjectBucket.key: str`](../../../cdm/backend/services/member_subject_overlay.py#L21)
- field: [`SubjectBucket.doc_count: int`](../../../cdm/backend/services/member_subject_overlay.py#L22)
- class: [`SubjectNames(BaseModel)`](../../../cdm/backend/services/member_subject_overlay.py#L25)
- field: [`SubjectNames.buckets: list[SubjectBucket]`](../../../cdm/backend/services/member_subject_overlay.py#L26)
- class: [`MemberSubjects(BaseModel)`](../../../cdm/backend/services/member_subject_overlay.py#L29)
- field: [`MemberSubjects.names: SubjectNames`](../../../cdm/backend/services/member_subject_overlay.py#L30)
- class: [`MemberBucket(BaseModel)`](../../../cdm/backend/services/member_subject_overlay.py#L33)
- field: [`MemberBucket.key: str`](../../../cdm/backend/services/member_subject_overlay.py#L34)
- field: [`MemberBucket.subjects: MemberSubjects`](../../../cdm/backend/services/member_subject_overlay.py#L35)
- class: [`MemberBuckets(BaseModel)`](../../../cdm/backend/services/member_subject_overlay.py#L38)
- field: [`MemberBuckets.buckets: list[MemberBucket]`](../../../cdm/backend/services/member_subject_overlay.py#L39)
- class: [`OverlayAggregations(BaseModel)`](../../../cdm/backend/services/member_subject_overlay.py#L42)
- field: [`OverlayAggregations.members: MemberBuckets`](../../../cdm/backend/services/member_subject_overlay.py#L43)
- class: [`OverlayResponse(BaseModel)`](../../../cdm/backend/services/member_subject_overlay.py#L46)
- field: [`OverlayResponse.aggregations: OverlayAggregations`](../../../cdm/backend/services/member_subject_overlay.py#L47)
- class: [`SubjectOverlay()`](../../../cdm/backend/services/member_subject_overlay.py#L50)
- function: [`SubjectOverlay.__init__(self, nodes: list[GraphSubjectNode], links: list[GraphSubjectLink]) -> None`](../../../cdm/backend/services/member_subject_overlay.py#L51)
- class: [`MemberSubjectOverlayBuilder()`](../../../cdm/backend/services/member_subject_overlay.py#L56)
- function: [`MemberSubjectOverlayBuilder.__init__(self, client: Elasticsearch) -> None`](../../../cdm/backend/services/member_subject_overlay.py#L57)
- function: [`MemberSubjectOverlayBuilder._search(self, member_ids: list[str], congress: int \| None) -> OverlayResponse`](../../../cdm/backend/services/member_subject_overlay.py#L60)
- field: [`MemberSubjectOverlayBuilder._search.filters: list[JsonObject]`](../../../cdm/backend/services/member_subject_overlay.py#L61)
- function: [`MemberSubjectOverlayBuilder.build(self, member_ids: list[str], congress: int \| None, per_member: int) -> SubjectOverlay`](../../../cdm/backend/services/member_subject_overlay.py#L87)
- field: [`MemberSubjectOverlayBuilder.build.links: list[GraphSubjectLink]`](../../../cdm/backend/services/member_subject_overlay.py#L91)

## cdm/backend/services/member_topic_overlay.py

[Source](../../../cdm/backend/services/member_topic_overlay.py)

- class: [`TopicOverlay()`](../../../cdm/backend/services/member_topic_overlay.py#L14)
- function: [`TopicOverlay.__init__(self, nodes: list[GraphTopicNode], links: list[GraphTopicLink]) -> None`](../../../cdm/backend/services/member_topic_overlay.py#L15)
- class: [`MemberTopicOverlayBuilder()`](../../../cdm/backend/services/member_topic_overlay.py#L22)
- function: [`MemberTopicOverlayBuilder.__init__(self, bills: SponsoredBillReader, topics: TopicService) -> None`](../../../cdm/backend/services/member_topic_overlay.py#L23)
- function: [`MemberTopicOverlayBuilder.build(self, member_ids: list[str], congress: int \| None, per_member: int, version: str \| None) -> TopicOverlay`](../../../cdm/backend/services/member_topic_overlay.py#L27)
- field: [`MemberTopicOverlayBuilder.build.links: list[GraphTopicLink]`](../../../cdm/backend/services/member_topic_overlay.py#L39)

## cdm/backend/services/neighborhood_service.py

[Source](../../../cdm/backend/services/neighborhood_service.py)

- class: [`NeighborhoodQuery(BaseModel)`](../../../cdm/backend/services/neighborhood_service.py#L33)
- field: [`NeighborhoodQuery.seeds: list[str]`](../../../cdm/backend/services/neighborhood_service.py#L34)
- field: [`NeighborhoodQuery.weights: dict[Signal, float]`](../../../cdm/backend/services/neighborhood_service.py#L35)
- field: [`NeighborhoodQuery.congress: int \| None`](../../../cdm/backend/services/neighborhood_service.py#L36)
- field: [`NeighborhoodQuery.limit: int`](../../../cdm/backend/services/neighborhood_service.py#L37)
- field: [`NeighborhoodQuery.parties: set[PartyGroup]`](../../../cdm/backend/services/neighborhood_service.py#L38)
- field: [`NeighborhoodQuery.chamber: Chamber \| None`](../../../cdm/backend/services/neighborhood_service.py#L39)
- field: [`NeighborhoodQuery.include_topics: bool`](../../../cdm/backend/services/neighborhood_service.py#L40)
- field: [`NeighborhoodQuery.topics_per_member: int`](../../../cdm/backend/services/neighborhood_service.py#L41)
- field: [`NeighborhoodQuery.include_subjects: bool`](../../../cdm/backend/services/neighborhood_service.py#L42)
- field: [`NeighborhoodQuery.subjects_per_member: int`](../../../cdm/backend/services/neighborhood_service.py#L43)
- field: [`NeighborhoodQuery.include_metasubjects: bool`](../../../cdm/backend/services/neighborhood_service.py#L44)
- field: [`NeighborhoodQuery.metasubjects_per_member: int`](../../../cdm/backend/services/neighborhood_service.py#L45)
- function: [`NeighborhoodQuery.signals(self) -> list[Signal]`](../../../cdm/backend/services/neighborhood_service.py#L48)
- class: [`SignalScaler()`](../../../cdm/backend/services/neighborhood_service.py#L52)
- function: [`SignalScaler.__init__(self) -> None`](../../../cdm/backend/services/neighborhood_service.py#L55)
- function: [`SignalScaler.fit(self, signal: Signal, scores: list[float]) -> None`](../../../cdm/backend/services/neighborhood_service.py#L58)
- function: [`SignalScaler.apply(self, signal: Signal, score: float) -> float`](../../../cdm/backend/services/neighborhood_service.py#L62)
- class: [`NeighborhoodService()`](../../../cdm/backend/services/neighborhood_service.py#L72)
- function: [`NeighborhoodService.__init__(self, graph: GraphService, members: MemberService, topic_overlay: MemberTopicOverlayBuilder, subject_overlay: MemberSubjectOverlayBuilder, metasubject_overlay: MemberMetasubjectOverlayBuilder) -> None`](../../../cdm/backend/services/neighborhood_service.py#L73)
- function: [`NeighborhoodService._key(first: str, second: str) -> PairKey`](../../../cdm/backend/services/neighborhood_service.py#L88)
- function: [`NeighborhoodService._chamber_of(member: MemberSummary) -> Chamber \| None`](../../../cdm/backend/services/neighborhood_service.py#L92)
- function: [`NeighborhoodService._allowed(self, member: MemberSummary, query: NeighborhoodQuery) -> bool`](../../../cdm/backend/services/neighborhood_service.py#L100)
- function: [`NeighborhoodService._collect(self, pairs: dict[PairKey, dict[Signal, float]], edges: list[MemberEdge], signal: Signal, scaler: SignalScaler, congress: int \| None, topics: dict[PairKey, list[str]]) -> None`](../../../cdm/backend/services/neighborhood_service.py#L105)
- function: [`NeighborhoodService._blend(signal_scores: dict[Signal, float], query: NeighborhoodQuery) -> float`](../../../cdm/backend/services/neighborhood_service.py#L122)
- function: [`NeighborhoodService.allowed_members(self, member_ids: list[str], query: NeighborhoodQuery) -> dict[str, MemberSummary]`](../../../cdm/backend/services/neighborhood_service.py#L134)
- function: [`NeighborhoodService.links_among(self, member_ids: list[str], query: NeighborhoodQuery, snapshot: GraphReadSnapshot) -> list[GraphLink]`](../../../cdm/backend/services/neighborhood_service.py#L145)
- field: [`NeighborhoodService.links_among.pairs: dict[PairKey, dict[Signal, float]]`](../../../cdm/backend/services/neighborhood_service.py#L156)
- field: [`NeighborhoodService.links_among.topics: dict[PairKey, list[str]]`](../../../cdm/backend/services/neighborhood_service.py#L157)
- function: [`NeighborhoodService.neighborhood(self, query: NeighborhoodQuery) -> NeighborhoodResponse`](../../../cdm/backend/services/neighborhood_service.py#L184)
- field: [`NeighborhoodService.neighborhood.seed_edges: dict[Signal, list[MemberEdge]]`](../../../cdm/backend/services/neighborhood_service.py#L201)
- field: [`NeighborhoodService.neighborhood.pairs: dict[PairKey, dict[Signal, float]]`](../../../cdm/backend/services/neighborhood_service.py#L215)
- field: [`NeighborhoodService.neighborhood.topics: dict[PairKey, list[str]]`](../../../cdm/backend/services/neighborhood_service.py#L216)
- field: [`NeighborhoodService.neighborhood.candidates: dict[str, dict[str, float]]`](../../../cdm/backend/services/neighborhood_service.py#L221)
- field: [`NeighborhoodService.neighborhood.kept: list[str]`](../../../cdm/backend/services/neighborhood_service.py#L232)

## cdm/backend/services/party_service.py

[Source](../../../cdm/backend/services/party_service.py)

- class: [`PartyService()`](../../../cdm/backend/services/party_service.py#L21)
- function: [`PartyService.__init__(self, repository: PerspectiveRepository, config: PerspectiveConfig, publications: TopicPublicationStore) -> None`](../../../cdm/backend/services/party_service.py#L22)
- function: [`PartyService.overview(self, congress: int \| None) -> PartiesResponse`](../../../cdm/backend/services/party_service.py#L32)
- function: [`PartyService._analysis(self, version: str \| None, has_results: bool) -> AnalysisStatus`](../../../cdm/backend/services/party_service.py#L58)
- function: [`PartyService.topic(self, congress: int, topic_id: int) -> PartyTopicResponse \| None`](../../../cdm/backend/services/party_service.py#L64)
- function: [`PartyService._ranking(self, party: PartyGroup, topics: list[TopicPerspectives]) -> PartyRanking`](../../../cdm/backend/services/party_service.py#L82)
- function: [`PartyService._party_bills(topic: TopicPerspectives, party: PartyGroup) -> int`](../../../cdm/backend/services/party_service.py#L117)
- function: [`PartyService._bilateral(topics: list[TopicPerspectives]) -> list[BilateralTopicEntry]`](../../../cdm/backend/services/party_service.py#L123)

## cdm/backend/services/search_service.py

[Source](../../../cdm/backend/services/search_service.py)

- class: [`SearchService()`](../../../cdm/backend/services/search_service.py#L17)
- function: [`SearchService.__init__(self, client: Elasticsearch, states: StateService, reads: QueryReadConfig \| None=None) -> None`](../../../cdm/backend/services/search_service.py#L18)
- function: [`SearchService.search(self, q: str, types: str, limit: int) -> SearchResponse`](../../../cdm/backend/services/search_service.py#L28)
- field: [`SearchService.search.results: list[SearchResultItem]`](../../../cdm/backend/services/search_service.py#L40)
- function: [`SearchService.search_members(self, query: str, limit: int) -> list[SearchResultItem]`](../../../cdm/backend/services/search_service.py#L57)
- field: [`SearchService.search_members.items: list[SearchResultItem]`](../../../cdm/backend/services/search_service.py#L69)
- function: [`SearchService._search_bills(self, query: str, limit: int) -> list[SearchResultItem]`](../../../cdm/backend/services/search_service.py#L98)
- field: [`SearchService._search_bills.items: list[SearchResultItem]`](../../../cdm/backend/services/search_service.py#L108)
- function: [`SearchService._state_results(self, query: str, limit: int) -> list[SearchResultItem]`](../../../cdm/backend/services/search_service.py#L132)
- field: [`SearchService._state_results.results: list[SearchResultItem]`](../../../cdm/backend/services/search_service.py#L136)
- function: [`SearchService._normalize_member_id(raw_id: str) -> str`](../../../cdm/backend/services/search_service.py#L152)
- function: [`SearchService._member_query(query: str, size: int) -> JsonObject`](../../../cdm/backend/services/search_service.py#L158)
- field: [`SearchService._member_query.should: list[JsonObject]`](../../../cdm/backend/services/search_service.py#L159)
- function: [`SearchService._bill_query(query: str, size: int) -> JsonObject`](../../../cdm/backend/services/search_service.py#L195)
- field: [`SearchService._bill_query.should: list[JsonObject]`](../../../cdm/backend/services/search_service.py#L203)

## cdm/backend/services/similar_bill_service.py

[Source](../../../cdm/backend/services/similar_bill_service.py)

- class: [`SimilarBillService()`](../../../cdm/backend/services/similar_bill_service.py#L15)
- function: [`SimilarBillService.__init__(self, client: Elasticsearch, store: EmbeddingStore, publications: TopicPublicationStore) -> None`](../../../cdm/backend/services/similar_bill_service.py#L16)
- function: [`SimilarBillService.similar(self, bill_id: str, size: int) -> SimilarBillsResponse`](../../../cdm/backend/services/similar_bill_service.py#L26)

## cdm/backend/services/sponsored_bills.py

[Source](../../../cdm/backend/services/sponsored_bills.py)

- class: [`SponsoredBillReader()`](../../../cdm/backend/services/sponsored_bills.py#L15)
- function: [`SponsoredBillReader.__init__(self, client: Elasticsearch) -> None`](../../../cdm/backend/services/sponsored_bills.py#L16)
- function: [`SponsoredBillReader.by_member(self, member_ids: list[str], congress: int \| None) -> dict[str, list[str]]`](../../../cdm/backend/services/sponsored_bills.py#L19)
- field: [`SponsoredBillReader.by_member.filters: list[JsonObject]`](../../../cdm/backend/services/sponsored_bills.py#L20)
- field: [`SponsoredBillReader.by_member.bills: dict[str, list[str]]`](../../../cdm/backend/services/sponsored_bills.py#L26)

## cdm/backend/services/state_service.py

[Source](../../../cdm/backend/services/state_service.py)

- class: [`StateService()`](../../../cdm/backend/services/state_service.py#L75)
- function: [`StateService.__init__(self, client: Elasticsearch) -> None`](../../../cdm/backend/services/state_service.py#L76)
- function: [`StateService.list_states(self) -> list[StateSummary]`](../../../cdm/backend/services/state_service.py#L80)
- function: [`StateService.get_districts(self, state_code: str) -> dict[str, Any]`](../../../cdm/backend/services/state_service.py#L88)
- function: [`StateService.get_timeline(self, state_code: str, from_congress: int \| None, to_congress: int \| None) -> StateTimelineResponse`](../../../cdm/backend/services/state_service.py#L94)
- field: [`StateService.get_timeline.house_members: list[TimelineMember]`](../../../cdm/backend/services/state_service.py#L102)
- field: [`StateService.get_timeline.senate_members: list[TimelineMember]`](../../../cdm/backend/services/state_service.py#L103)
- field: [`StateService.get_timeline.seen_terms: set[tuple[str, str, int, int]]`](../../../cdm/backend/services/state_service.py#L104)
- function: [`StateService._member_records(self) -> list[dict[str, Any]]`](../../../cdm/backend/services/state_service.py#L175)
- function: [`StateService._fetch_districts(self, state_code: str) -> dict[str, Any]`](../../../cdm/backend/services/state_service.py#L184)
- function: [`StateService._congress_for_year(year: int) -> int`](../../../cdm/backend/services/state_service.py#L210)
- function: [`StateService._group_members(members: list[TimelineMember], from_congress: int \| None, to_congress: int \| None) -> list[CongressGroup]`](../../../cdm/backend/services/state_service.py#L214)
- field: [`StateService._group_members.groups: dict[int, dict[str, TimelineMember]]`](../../../cdm/backend/services/state_service.py#L219)

## cdm/backend/services/subject_service.py

[Source](../../../cdm/backend/services/subject_service.py)

- class: [`SubjectService()`](../../../cdm/backend/services/subject_service.py#L30)
- function: [`SubjectService.__init__(self, client: Any) -> None`](../../../cdm/backend/services/subject_service.py#L31)
- function: [`SubjectService.list_subjects(self, congress: int \| None=None, size: int=100) -> SubjectsResponse`](../../../cdm/backend/services/subject_service.py#L34)
- field: [`SubjectService.list_subjects.filters: list[dict[str, Any]]`](../../../cdm/backend/services/subject_service.py#L38)
- function: [`SubjectService.list_policy_area_trends(self, *, size: int=10, start_year: int \| None=None) -> PolicyAreaTrendsResponse`](../../../cdm/backend/services/subject_service.py#L55)
- field: [`SubjectService.list_policy_area_trends.filters: list[dict[str, Any]]`](../../../cdm/backend/services/subject_service.py#L63)
- field: [`SubjectService.list_policy_area_trends.raw: dict[str, tuple[int, dict[int, int]]]`](../../../cdm/backend/services/subject_service.py#L97)
- field: [`SubjectService.list_policy_area_trends.years: set[int]`](../../../cdm/backend/services/subject_service.py#L98)
- field: [`SubjectService.list_policy_area_trends.counts: dict[int, int]`](../../../cdm/backend/services/subject_service.py#L100)
- function: [`SubjectService.member_subject_items(self, bioguide_id: str, size: int=25) -> tuple[list[TopicItem], list[TopicItem]]`](../../../cdm/backend/services/subject_service.py#L126)
- field: [`SubjectService.member_subject_items.filters: list[dict[str, Any]]`](../../../cdm/backend/services/subject_service.py#L130)
- function: [`SubjectService._aggregate(self, filters: list[dict[str, Any]], size: int) -> dict[str, Any] \| None`](../../../cdm/backend/services/subject_service.py#L148)
- function: [`SubjectService._buckets(response: dict[str, Any] \| None, *path: str) -> list[dict[str, Any]]`](../../../cdm/backend/services/subject_service.py#L177)
- field: [`SubjectService._buckets.node: Any`](../../../cdm/backend/services/subject_service.py#L180)
- function: [`SubjectService._weighted(buckets: list[dict[str, Any]]) -> list[TopicItem]`](../../../cdm/backend/services/subject_service.py#L186)

## cdm/backend/services/topic_neighborhood_service.py

[Source](../../../cdm/backend/services/topic_neighborhood_service.py)

- class: [`TopicNeighborhoodQuery(BaseModel)`](../../../cdm/backend/services/topic_neighborhood_service.py#L37)
- field: [`TopicNeighborhoodQuery.kind: CenterKind`](../../../cdm/backend/services/topic_neighborhood_service.py#L38)
- field: [`TopicNeighborhoodQuery.key: str`](../../../cdm/backend/services/topic_neighborhood_service.py#L39)
- field: [`TopicNeighborhoodQuery.neighborhood: NeighborhoodQuery`](../../../cdm/backend/services/topic_neighborhood_service.py#L40)
- class: [`TopicNeighborhoodService()`](../../../cdm/backend/services/topic_neighborhood_service.py#L43)
- function: [`TopicNeighborhoodService.__init__(self, neighborhoods: NeighborhoodService, topics: TopicService, assigned: AssignedBillReader, sponsors: TopicSponsorReader) -> None`](../../../cdm/backend/services/topic_neighborhood_service.py#L44)
- function: [`TopicNeighborhoodService._counts(self, query: TopicNeighborhoodQuery, version: str \| None) -> Counter[str]`](../../../cdm/backend/services/topic_neighborhood_service.py#L56)
- function: [`TopicNeighborhoodService._label(self, query: TopicNeighborhoodQuery, version: str \| None) -> str`](../../../cdm/backend/services/topic_neighborhood_service.py#L72)
- function: [`TopicNeighborhoodService.neighborhood(self, query: TopicNeighborhoodQuery) -> NeighborhoodResponse`](../../../cdm/backend/services/topic_neighborhood_service.py#L82)

## cdm/backend/services/topic_service.py

[Source](../../../cdm/backend/services/topic_service.py)

- function: [`_quarter(date: str) -> str`](../../../cdm/backend/services/topic_service.py#L48)
- class: [`TopicService()`](../../../cdm/backend/services/topic_service.py#L54)
- function: [`TopicService.__init__(self, client: Elasticsearch, analysis_index: str, subjects: SubjectService, publications: TopicPublicationStore \| None=None, read_config: TopicReadConfig \| None=None) -> None`](../../../cdm/backend/services/topic_service.py#L55)
- function: [`TopicService.latest_model_version(self) -> tuple[str \| None, str \| None]`](../../../cdm/backend/services/topic_service.py#L71)
- function: [`TopicService.topic_summaries(self, model_version: str) -> dict[int, TopicSummary]`](../../../cdm/backend/services/topic_service.py#L75)
- field: [`TopicService.topic_summaries.summaries: dict[int, TopicSummary]`](../../../cdm/backend/services/topic_service.py#L89)
- function: [`TopicService.member_assignments(self, bill_ids: list[str], model_version: str) -> list[tuple[str, int]]`](../../../cdm/backend/services/topic_service.py#L115)
- field: [`TopicService.member_assignments.pairs: list[tuple[str, int]]`](../../../cdm/backend/services/topic_service.py#L119)
- function: [`TopicService.member_metasubject_assignments(self, bill_ids: list[str], model_version: str) -> list[tuple[str, int]]`](../../../cdm/backend/services/topic_service.py#L144)
- field: [`TopicService.member_metasubject_assignments.pairs: list[tuple[str, int]]`](../../../cdm/backend/services/topic_service.py#L148)
- function: [`TopicService.list_metasubjects(self) -> MetasubjectsResponse`](../../../cdm/backend/services/topic_service.py#L173)
- function: [`TopicService.list_metasubject_trends(self) -> MetasubjectTrendsResponse`](../../../cdm/backend/services/topic_service.py#L189)
- function: [`TopicService.get_metasubject(self, metasubject_id: int) -> MetasubjectDetailResponse \| None`](../../../cdm/backend/services/topic_service.py#L214)
- function: [`TopicService.related_metasubjects(self, model_version: str, metasubject_id: int) -> list[RelatedMetasubject]`](../../../cdm/backend/services/topic_service.py#L240)
- function: [`TopicService._nearest(target_id: int, centroids: dict[int, np.ndarray], limit: int) -> list[tuple[int, float]]`](../../../cdm/backend/services/topic_service.py#L282)
- function: [`TopicService.related_topics(self, model_version: str, topic_id: int, summaries: dict[int, TopicSummary]) -> list[RelatedTopic]`](../../../cdm/backend/services/topic_service.py#L300)
- function: [`TopicService.list_topics(self) -> TopicsResponse`](../../../cdm/backend/services/topic_service.py#L338)
- function: [`TopicService.list_topic_trends(self, *, size: int=8) -> TopicTrendsResponse`](../../../cdm/backend/services/topic_service.py#L360)
- field: [`TopicService.list_topic_trends.points: dict[int, list[TopicTrendPoint]]`](../../../cdm/backend/services/topic_service.py#L393)
- function: [`TopicService.get_topic(self, topic_id: int, *, top_bills: int=20) -> TopicDetailResponse \| None`](../../../cdm/backend/services/topic_service.py#L421)
- function: [`TopicService.get_bill_topics(self, bill_id: str) -> BillTopicsResponse`](../../../cdm/backend/services/topic_service.py#L494)
- function: [`TopicService.get_member_topics(self, bioguide_id: str) -> MemberTopicsResponse`](../../../cdm/backend/services/topic_service.py#L540)
- function: [`TopicService.get_member_topics.label_of(topic_id: int) -> str`](../../../cdm/backend/services/topic_service.py#L567)
- field: [`TopicService.get_member_topics.totals: Counter[int]`](../../../cdm/backend/services/topic_service.py#L574)
- field: [`TopicService.get_member_topics.buckets: dict[tuple[str, int], int]`](../../../cdm/backend/services/topic_service.py#L585)
- function: [`TopicService._search(self, body: dict[str, Any]) -> dict[str, Any]`](../../../cdm/backend/services/topic_service.py#L611)
- function: [`TopicService._hits(response: dict[str, Any] \| None) -> list[dict[str, Any]]`](../../../cdm/backend/services/topic_service.py#L619)
- function: [`TopicService.metasubject_summaries(self, model_version: str) -> dict[int, MetasubjectSummary]`](../../../cdm/backend/services/topic_service.py#L624)
- function: [`TopicService._metasubject_points(self, model_version: str, metasubject_ids: list[int] \| None=None) -> dict[int, list[TopicTrendPoint]]`](../../../cdm/backend/services/topic_service.py#L658)
- field: [`TopicService._metasubject_points.filters: list[dict[str, Any]]`](../../../cdm/backend/services/topic_service.py#L661)
- field: [`TopicService._metasubject_points.points: dict[int, list[TopicTrendPoint]]`](../../../cdm/backend/services/topic_service.py#L674)
- function: [`TopicService._bill_titles(self, bill_ids: list[str]) -> dict[str, str]`](../../../cdm/backend/services/topic_service.py#L685)
- function: [`TopicService._member_bill_dates(self, bioguide_id: str) -> dict[str, str \| None]`](../../../cdm/backend/services/topic_service.py#L701)

## cdm/backend/services/topic_sponsors.py

[Source](../../../cdm/backend/services/topic_sponsors.py)

- class: [`CenterKind(StrEnum)`](../../../cdm/backend/services/topic_sponsors.py#L23)
- class: [`AssignmentField(StrEnum)`](../../../cdm/backend/services/topic_sponsors.py#L29)
- class: [`SponsorBucket(BaseModel)`](../../../cdm/backend/services/topic_sponsors.py#L34)
- field: [`SponsorBucket.key: str`](../../../cdm/backend/services/topic_sponsors.py#L35)
- field: [`SponsorBucket.doc_count: int`](../../../cdm/backend/services/topic_sponsors.py#L36)
- class: [`SponsorAggregation(BaseModel)`](../../../cdm/backend/services/topic_sponsors.py#L39)
- field: [`SponsorAggregation.buckets: list[SponsorBucket]`](../../../cdm/backend/services/topic_sponsors.py#L40)
- class: [`SponsorAggregations(BaseModel)`](../../../cdm/backend/services/topic_sponsors.py#L43)
- field: [`SponsorAggregations.sponsors: SponsorAggregation`](../../../cdm/backend/services/topic_sponsors.py#L44)
- class: [`SponsorResponse(BaseModel)`](../../../cdm/backend/services/topic_sponsors.py#L47)
- field: [`SponsorResponse.aggregations: SponsorAggregations`](../../../cdm/backend/services/topic_sponsors.py#L48)
- class: [`AssignedBillReader()`](../../../cdm/backend/services/topic_sponsors.py#L51)
- function: [`AssignedBillReader.__init__(self, client: Elasticsearch, analysis_index: str) -> None`](../../../cdm/backend/services/topic_sponsors.py#L54)
- function: [`AssignedBillReader.read(self, field: AssignmentField, value: int, model_version: str) -> list[str]`](../../../cdm/backend/services/topic_sponsors.py#L58)
- class: [`TopicSponsorReader()`](../../../cdm/backend/services/topic_sponsors.py#L82)
- function: [`TopicSponsorReader.__init__(self, client: Elasticsearch) -> None`](../../../cdm/backend/services/topic_sponsors.py#L83)
- function: [`TopicSponsorReader._count(self, query: JsonObject) -> Counter[str]`](../../../cdm/backend/services/topic_sponsors.py#L86)
- function: [`TopicSponsorReader._filters(congress: int \| None) -> list[JsonObject]`](../../../cdm/backend/services/topic_sponsors.py#L102)
- field: [`TopicSponsorReader._filters.filters: list[JsonObject]`](../../../cdm/backend/services/topic_sponsors.py#L103)
- function: [`TopicSponsorReader.by_bill_ids(self, bill_ids: Iterable[str], congress: int \| None) -> Counter[str]`](../../../cdm/backend/services/topic_sponsors.py#L108)
- field: [`TopicSponsorReader.by_bill_ids.totals: Counter[str]`](../../../cdm/backend/services/topic_sponsors.py#L110)
- function: [`TopicSponsorReader.by_subject(self, subject: str, congress: int \| None) -> Counter[str]`](../../../cdm/backend/services/topic_sponsors.py#L117)

## cdm/backend/services/vote_breakdown_service.py

[Source](../../../cdm/backend/services/vote_breakdown_service.py)

- field: [`_POSITION_FIELDS: dict[VotePosition, str]`](../../../cdm/backend/services/vote_breakdown_service.py#L19)
- class: [`VoteBreakdownService()`](../../../cdm/backend/services/vote_breakdown_service.py#L37)
- function: [`VoteBreakdownService.__init__(self, client: Elasticsearch) -> None`](../../../cdm/backend/services/vote_breakdown_service.py#L40)
- function: [`VoteBreakdownService.for_vote(self, vote_id: str) -> VoteBreakdownResponse \| None`](../../../cdm/backend/services/vote_breakdown_service.py#L43)
- field: [`VoteBreakdownService.for_vote.source: dict[str, Any]`](../../../cdm/backend/services/vote_breakdown_service.py#L48)
- field: [`VoteBreakdownService.for_vote.grouped: dict[PartyGroup, dict[VotePosition, list[VoteMember]]]`](../../../cdm/backend/services/vote_breakdown_service.py#L57)
- function: [`VoteBreakdownService._members(self, ids: list[str]) -> dict[str, tuple[PartyGroup, VoteMember]]`](../../../cdm/backend/services/vote_breakdown_service.py#L87)
- field: [`VoteBreakdownService._members.found: dict[str, tuple[PartyGroup, VoteMember]]`](../../../cdm/backend/services/vote_breakdown_service.py#L96)
- field: [`VoteBreakdownService._members.source: dict[str, Any]`](../../../cdm/backend/services/vote_breakdown_service.py#L98)

## cdm/backend/services/vote_service.py

[Source](../../../cdm/backend/services/vote_service.py)

- class: [`VoteService()`](../../../cdm/backend/services/vote_service.py#L46)
- function: [`VoteService.__init__(self, client: Elasticsearch) -> None`](../../../cdm/backend/services/vote_service.py#L49)
- function: [`VoteService.for_bill(self, bill_id: str, limit: int=100) -> BillVotesResponse`](../../../cdm/backend/services/vote_service.py#L52)
- field: [`VoteService.for_bill.merged: dict[_DedupeKey, VoteSummary]`](../../../cdm/backend/services/vote_service.py#L58)
- function: [`VoteService._dedupe_key(vote: VoteSummary) -> _DedupeKey`](../../../cdm/backend/services/vote_service.py#L72)
- function: [`VoteService._rollcall_votes(self, key: BillKey, limit: int) -> list[VoteSummary]`](../../../cdm/backend/services/vote_service.py#L75)
- function: [`VoteService._house_votes(self, key: BillKey, limit: int) -> list[VoteSummary]`](../../../cdm/backend/services/vote_service.py#L85)
- function: [`VoteService._rollcall_summary(hit: dict[str, Any]) -> VoteSummary`](../../../cdm/backend/services/vote_service.py#L95)
- field: [`VoteService._rollcall_summary.source: dict[str, Any]`](../../../cdm/backend/services/vote_service.py#L96)
- function: [`VoteService._house_summary(hit: dict[str, Any]) -> VoteSummary`](../../../cdm/backend/services/vote_service.py#L121)
- field: [`VoteService._house_summary.source: dict[str, Any]`](../../../cdm/backend/services/vote_service.py#L122)

# composition source reference

[All source areas](README.md)

Generated from declarations; see the catalogue scope in the index.

## cdm/__init__.py

[Source](../../../cdm/__init__.py)

No declarations in this module.


## cdm/container.py

[Source](../../../cdm/container.py)

- class: [`Container()`](../../../cdm/container.py#L49)
- function: [`Container.__init__(self, config: AppConfig) -> None`](../../../cdm/container.py#L56)
- function: [`Container.job_store(self) -> JobStore`](../../../cdm/container.py#L60)
- function: [`Container.job_dispatcher(self) -> JobDispatcher`](../../../cdm/container.py#L64)
- function: [`Container.job_submitter(self) -> JobSubmitter`](../../../cdm/container.py#L68)
- function: [`Container.analytics_jobs(self) -> AnalyticsJobs`](../../../cdm/container.py#L72)
- function: [`Container.elastic_client(self) -> Elasticsearch`](../../../cdm/container.py#L76)
- function: [`Container.ollama_client(self) -> OllamaClient`](../../../cdm/container.py#L80)
- function: [`Container.topic_labeler(self) -> TopicLabeler`](../../../cdm/container.py#L84)
- function: [`Container.embedding_store(self, model: str \| None=None, *, index: str \| None=None) -> EmbeddingStore`](../../../cdm/container.py#L87)
- function: [`Container.topic_publications(self) -> TopicPublicationStore`](../../../cdm/container.py#L104)
- function: [`Container.retirement_reporter(self) -> RetirementReporter`](../../../cdm/container.py#L110)
- function: [`Container.perspective_repository(self) -> PerspectiveRepository`](../../../cdm/container.py#L118)
- function: [`Container.party_service(self) -> PartyService`](../../../cdm/container.py#L124)
- function: [`Container.similar_bill_service(self) -> SimilarBillService`](../../../cdm/container.py#L132)
- function: [`Container.committee_service(self) -> CommitteeService`](../../../cdm/container.py#L140)
- function: [`Container.bill_service(self) -> BillService`](../../../cdm/container.py#L144)
- function: [`Container.vote_service(self) -> VoteService`](../../../cdm/container.py#L152)
- function: [`Container.vote_breakdown_service(self) -> VoteBreakdownService`](../../../cdm/container.py#L156)
- function: [`Container.state_service(self) -> StateService`](../../../cdm/container.py#L160)
- function: [`Container.search_service(self) -> SearchService`](../../../cdm/container.py#L164)
- function: [`Container.subject_service(self) -> SubjectService`](../../../cdm/container.py#L170)
- function: [`Container.topic_service(self) -> TopicService`](../../../cdm/container.py#L174)
- function: [`Container.member_service(self) -> MemberService`](../../../cdm/container.py#L183)
- function: [`Container.jobs_engine(self) -> Engine`](../../../cdm/container.py#L189)
- function: [`Container.admin_service(self) -> AdminService`](../../../cdm/container.py#L193)
- function: [`Container.graph_service(self) -> GraphService`](../../../cdm/container.py#L197)
- function: [`Container.sponsored_bills(self) -> SponsoredBillReader`](../../../cdm/container.py#L206)
- function: [`Container.neighborhood_service(self) -> NeighborhoodService`](../../../cdm/container.py#L210)
- function: [`Container.topic_neighborhood_service(self) -> TopicNeighborhoodService`](../../../cdm/container.py#L220)

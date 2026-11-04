# workers source reference

[All source areas](README.md)

Generated from declarations; see the catalogue scope in the index.

## cdm/workers/__init__.py

[Source](../../../cdm/workers/__init__.py)

No declarations in this module.


## cdm/workers/analytics_runner.py

[Source](../../../cdm/workers/analytics_runner.py)

- class: [`AnalysisCancelled(Exception)`](../../../cdm/workers/analytics_runner.py#L22)
- class: [`AnalyticsJobRunner()`](../../../cdm/workers/analytics_runner.py#L26)
- function: [`AnalyticsJobRunner.__init__(self, store: JobStore, training: Callable[[TopicTrainingOptions, Callable[[AnalysisProgress], None]], TopicTrainingJob], graph: Callable[[Callable[[AnalysisProgress], None]], GraphBuildJob], perspectives: Callable[[PerspectiveRequest, Callable[[AnalysisProgress], None]], PerspectiveBuildJob]) -> None`](../../../cdm/workers/analytics_runner.py#L27)
- function: [`AnalyticsJobRunner.run(self, job_id: str) -> JobResult`](../../../cdm/workers/analytics_runner.py#L44)
- function: [`AnalyticsJobRunner.run.report(update: AnalysisProgress) -> None`](../../../cdm/workers/analytics_runner.py#L53)

## cdm/workers/celery_app.py

[Source](../../../cdm/workers/celery_app.py)

No declarations in this module.


## cdm/workers/dispatch.py

[Source](../../../cdm/workers/dispatch.py)

- class: [`TaskName(StrEnum)`](../../../cdm/workers/dispatch.py#L16)
- class: [`JobDispatcher()`](../../../cdm/workers/dispatch.py#L25)
- function: [`JobDispatcher.__init__(self, app: Celery, queues: QueueConfig) -> None`](../../../cdm/workers/dispatch.py#L28)
- function: [`JobDispatcher.dispatch(self, kind: str, job_id: str, *, countdown: int \| None=None) -> None`](../../../cdm/workers/dispatch.py#L55)
- class: [`JobSubmitter()`](../../../cdm/workers/dispatch.py#L70)
- function: [`JobSubmitter.__init__(self, store: JobStore, dispatcher: JobDispatcher) -> None`](../../../cdm/workers/dispatch.py#L73)
- function: [`JobSubmitter.job_id(kind: str, payload: JsonObject) -> str`](../../../cdm/workers/dispatch.py#L78)
- function: [`JobSubmitter.exists(self, kind: str, payload: JsonObject) -> bool`](../../../cdm/workers/dispatch.py#L83)
- function: [`JobSubmitter.submit(self, kind: str, payload: JsonObject, *, dispatch_existing: bool=True, dispatch: bool=True) -> JobRow`](../../../cdm/workers/dispatch.py#L90)
- field: [`JobSubmitter.submit.existing: JobRow \| None`](../../../cdm/workers/dispatch.py#L99)

## cdm/workers/failures.py

[Source](../../../cdm/workers/failures.py)

- class: [`FailureClassifier()`](../../../cdm/workers/failures.py#L11)
- function: [`FailureClassifier.is_transient(self, exc: BaseException) -> bool`](../../../cdm/workers/failures.py#L60)
- function: [`FailureClassifier.is_retryable_error(self, error: str \| None) -> bool`](../../../cdm/workers/failures.py#L80)

## cdm/workers/govinfo_runner.py

[Source](../../../cdm/workers/govinfo_runner.py)

- class: [`GovInfoCollection(StrEnum)`](../../../cdm/workers/govinfo_runner.py#L41)
- class: [`GovInfoRecordParser(Protocol)`](../../../cdm/workers/govinfo_runner.py#L47)
- function: [`GovInfoRecordParser.parse(self, xml: bytes \| str, package: GovInfoPackage) -> JsonObject`](../../../cdm/workers/govinfo_runner.py#L48)
- class: [`GovInfoCollectionSpec()`](../../../cdm/workers/govinfo_runner.py#L51)
- function: [`GovInfoCollectionSpec.__init__(self, parser: GovInfoRecordParser, resource: str, parser_version: str) -> None`](../../../cdm/workers/govinfo_runner.py#L54)
- class: [`GovInfoPackageRunner()`](../../../cdm/workers/govinfo_runner.py#L62)
- function: [`GovInfoPackageRunner.__init__(self, store: JobStore, redis_client: Redis, submitter: JobSubmitter, dispatcher: JobDispatcher, redis_config: RedisConfig, session: requests.Session, rate_limiter: TokenBucket) -> None`](../../../cdm/workers/govinfo_runner.py#L65)
- function: [`GovInfoPackageRunner.run(self, job_id: str) -> JobResult`](../../../cdm/workers/govinfo_runner.py#L94)
- class: [`GovInfoBatchRunner()`](../../../cdm/workers/govinfo_runner.py#L198)
- function: [`GovInfoBatchRunner.__init__(self, store: JobStore, dispatcher: JobDispatcher) -> None`](../../../cdm/workers/govinfo_runner.py#L201)
- function: [`GovInfoBatchRunner.run(self, batch_id: str) -> JobResult`](../../../cdm/workers/govinfo_runner.py#L205)
- class: [`ReconciliationRunner()`](../../../cdm/workers/govinfo_runner.py#L216)
- function: [`ReconciliationRunner.__init__(self, store: JobStore, client: Elasticsearch) -> None`](../../../cdm/workers/govinfo_runner.py#L219)
- function: [`ReconciliationRunner.run(self, job_id: str) -> JobResult`](../../../cdm/workers/govinfo_runner.py#L223)

## cdm/workers/heartbeat.py

[Source](../../../cdm/workers/heartbeat.py)

- class: [`JobHeartbeat()`](../../../cdm/workers/heartbeat.py#L15)
- function: [`JobHeartbeat.__init__(self, store: JobStore, interval_seconds: float) -> None`](../../../cdm/workers/heartbeat.py#L18)
- function: [`JobHeartbeat.watch(self, job_id: str) -> Iterator[None]`](../../../cdm/workers/heartbeat.py#L23)
- function: [`JobHeartbeat._beat(self, job_id: str, stop: threading.Event) -> None`](../../../cdm/workers/heartbeat.py#L35)

## cdm/workers/index_runner.py

[Source](../../../cdm/workers/index_runner.py)

- class: [`ArchiveReplayer()`](../../../cdm/workers/index_runner.py#L22)
- function: [`ArchiveReplayer.__init__(self, client: Elasticsearch) -> None`](../../../cdm/workers/index_runner.py#L25)
- function: [`ArchiveReplayer.replay(self, payload: IndexPayload) -> int`](../../../cdm/workers/index_runner.py#L28)
- class: [`IndexJobRunner()`](../../../cdm/workers/index_runner.py#L56)
- function: [`IndexJobRunner.__init__(self, store: JobStore, redis_client: Redis, client: Elasticsearch, indexing: IndexingConfig, default_group: str) -> None`](../../../cdm/workers/index_runner.py#L57)
- function: [`IndexJobRunner.run(self, job_id: str) -> JobResult`](../../../cdm/workers/index_runner.py#L76)
- function: [`IndexJobRunner._claim_batch(self, job_id: str, payload: IndexPayload) -> list[JobRow]`](../../../cdm/workers/index_runner.py#L94)
- function: [`IndexJobRunner._index(self, payload: IndexPayload, jobs: dict[str, IndexPayload]) -> dict[str, IndexOutcome \| Exception]`](../../../cdm/workers/index_runner.py#L107)
- function: [`IndexJobRunner._finalize(self, job_id: str, jobs: dict[str, IndexPayload], outcomes: dict[str, IndexOutcome \| Exception]) -> JobResult`](../../../cdm/workers/index_runner.py#L127)
- field: [`IndexJobRunner._finalize.own_error: Exception \| None`](../../../cdm/workers/index_runner.py#L133)
- field: [`IndexJobRunner._finalize.own_result: IndexOutcome \| None`](../../../cdm/workers/index_runner.py#L134)
- function: [`IndexJobRunner._check_complete(self, payload: IndexPayload, outcome: IndexOutcome) -> None`](../../../cdm/workers/index_runner.py#L153)

## cdm/workers/ingest_runner.py

[Source](../../../cdm/workers/ingest_runner.py)

- class: [`IngestSession()`](../../../cdm/workers/ingest_runner.py#L31)
- function: [`IngestSession.__init__(self, job_id: str, store: JobStore, redis_client: Redis, redis_config: RedisConfig, archive: JsonlRecordArchive, quarantine: SQLiteQuarantineArchive, library: LatestRecordArchive \| None=None, flush_every: int=100, on_flush: Callable[[str, int], str \| None] \| None=None) -> None`](../../../cdm/workers/ingest_runner.py#L37)
- function: [`IngestSession.archive_record(self, resource: str, record: JsonObject) -> None`](../../../cdm/workers/ingest_runner.py#L63)
- function: [`IngestSession.publish_record(self, resource: str, record: JsonObject) -> None`](../../../cdm/workers/ingest_runner.py#L68)
- function: [`IngestSession.flush_resource(self, resource: str) -> None`](../../../cdm/workers/ingest_runner.py#L78)
- function: [`IngestSession.flush_all(self) -> None`](../../../cdm/workers/ingest_runner.py#L88)
- function: [`IngestSession.update_progress(self, resource: str, stage: CoverageStage, values: dict[str, int \| str \| None]) -> None`](../../../cdm/workers/ingest_runner.py#L92)
- function: [`IngestSession.quarantine_validation_failure(self, resource: str, record: JsonObject, error: str, source_url: str \| None) -> None`](../../../cdm/workers/ingest_runner.py#L104)
- class: [`IngestJobRunner()`](../../../cdm/workers/ingest_runner.py#L121)
- function: [`IngestJobRunner.__init__(self, store: JobStore, redis_client: Redis, submitter: JobSubmitter, redis_config: RedisConfig, congress_api: CongressApiConfig, bill_states: IndexedBillStateReader, library: RecordLibrary, rate_limiter: TokenBucket, partial_index_every: int, dispatcher: JobDispatcher, queues: QueueConfig) -> None`](../../../cdm/workers/ingest_runner.py#L125)
- function: [`IngestJobRunner.should_queue_index_job(cls, resource: str) -> bool`](../../../cdm/workers/ingest_runner.py#L152)
- function: [`IngestJobRunner.run(self, job_id: str) -> JobResult`](../../../cdm/workers/ingest_runner.py#L155)
- function: [`IngestJobRunner._library_archive(self, payload: IngestPayload) -> LatestRecordArchive \| None`](../../../cdm/workers/ingest_runner.py#L199)
- function: [`IngestJobRunner._item_filter(self, payload: IngestPayload) -> StaleBillFilter \| None`](../../../cdm/workers/ingest_runner.py#L207)
- function: [`IngestJobRunner._run_pipeline(self, payload: IngestPayload, job_outdir: Path, session: IngestSession) -> list[ResourceResult]`](../../../cdm/workers/ingest_runner.py#L212)
- function: [`IngestJobRunner._queue_index_jobs(self, job_id: str, payload: IngestPayload, job_outdir: Path, results: list[ResourceResult], session: IngestSession) -> list[str]`](../../../cdm/workers/ingest_runner.py#L248)
- function: [`IngestJobRunner._flush_index(self, job_id: str, payload: IngestPayload, job_outdir: Path, resource: str, attempt: int, part: int) -> str \| None`](../../../cdm/workers/ingest_runner.py#L272)
- function: [`IngestJobRunner._submit_index(self, job_id: str, payload: IngestPayload, job_outdir: Path, resource: str, expected_count: int \| None, *, attempt: int \| None=None, part: int \| None=None) -> str`](../../../cdm/workers/ingest_runner.py#L287)

## cdm/workers/maintenance.py

[Source](../../../cdm/workers/maintenance.py)

- class: [`QueueDepthProbe()`](../../../cdm/workers/maintenance.py#L26)
- function: [`QueueDepthProbe.__init__(self, app: Celery) -> None`](../../../cdm/workers/maintenance.py#L29)
- function: [`QueueDepthProbe.depth(self, queue: str) -> int \| None`](../../../cdm/workers/maintenance.py#L32)
- class: [`ActiveJobProbe()`](../../../cdm/workers/maintenance.py#L45)
- function: [`ActiveJobProbe.__init__(self, app: Celery, timeout_seconds: float=5.0) -> None`](../../../cdm/workers/maintenance.py#L48)
- function: [`ActiveJobProbe.job_ids(self) -> set[str]`](../../../cdm/workers/maintenance.py#L52)
- class: [`RecoveryResult(BaseModel)`](../../../cdm/workers/maintenance.py#L67)
- field: [`RecoveryResult.recovered: list[str]`](../../../cdm/workers/maintenance.py#L68)
- field: [`RecoveryResult.skipped: str \| None`](../../../cdm/workers/maintenance.py#L69)
- class: [`JobRecoveryService()`](../../../cdm/workers/maintenance.py#L72)
- function: [`JobRecoveryService.__init__(self, store: JobStore, redis_client: Redis, dispatcher: JobDispatcher, probe: QueueDepthProbe, classifier: FailureClassifier, queues: QueueConfig, active_jobs: ActiveJobProbe) -> None`](../../../cdm/workers/maintenance.py#L110)
- function: [`JobRecoveryService.index_redispatch_budget(self) -> int`](../../../cdm/workers/maintenance.py#L128)
- function: [`JobRecoveryService.recover(self) -> RecoveryResult`](../../../cdm/workers/maintenance.py#L134)
- function: [`JobRecoveryService._candidates(self) -> list[JobRow]`](../../../cdm/workers/maintenance.py#L145)
- function: [`JobRecoveryService._stale_active(self, now: datetime) -> list[JobRow]`](../../../cdm/workers/maintenance.py#L173)
- function: [`JobRecoveryService._failed_candidates(self) -> list[JobRow]`](../../../cdm/workers/maintenance.py#L184)
- function: [`JobRecoveryService._batched_package_ids(self) -> set[str]`](../../../cdm/workers/maintenance.py#L200)
- field: [`JobRecoveryService._batched_package_ids.ids: set[str]`](../../../cdm/workers/maintenance.py#L201)
- function: [`JobRecoveryService._requeue(self, candidates: list[JobRow]) -> list[str]`](../../../cdm/workers/maintenance.py#L209)
- field: [`JobRecoveryService._requeue.recovered: list[str]`](../../../cdm/workers/maintenance.py#L211)
- field: [`JobRecoveryService._requeue.seen: set[str]`](../../../cdm/workers/maintenance.py#L212)
- class: [`RetentionResult(BaseModel)`](../../../cdm/workers/maintenance.py#L239)
- field: [`RetentionResult.pruned_jobs: int`](../../../cdm/workers/maintenance.py#L240)
- field: [`RetentionResult.streams_deleted: int`](../../../cdm/workers/maintenance.py#L241)
- field: [`RetentionResult.archives_deleted: int`](../../../cdm/workers/maintenance.py#L242)
- field: [`RetentionResult.orphan_archives_deleted: int`](../../../cdm/workers/maintenance.py#L243)
- field: [`RetentionResult.orphan_bytes_freed: int`](../../../cdm/workers/maintenance.py#L244)
- field: [`RetentionResult.vacuumed: bool`](../../../cdm/workers/maintenance.py#L245)
- field: [`RetentionResult.protected: list[str]`](../../../cdm/workers/maintenance.py#L246)
- class: [`RetentionService()`](../../../cdm/workers/maintenance.py#L249)
- function: [`RetentionService.__init__(self, store: JobStore, redis_client: Redis, ledger: LedgerConfig, govinfo: GovInfoConfig, data_root: Path=Path('data')) -> None`](../../../cdm/workers/maintenance.py#L261)
- function: [`RetentionService.stream_source_job_id(cls, stream_name: str) -> str \| None`](../../../cdm/workers/maintenance.py#L276)
- function: [`RetentionService.run(self) -> RetentionResult`](../../../cdm/workers/maintenance.py#L284)
- function: [`RetentionService._protected_job_ids(self) -> set[str]`](../../../cdm/workers/maintenance.py#L309)
- field: [`RetentionService._protected_job_ids.protected: set[str]`](../../../cdm/workers/maintenance.py#L310)
- function: [`RetentionService._delete_streams(self, protected: set[str], pruned_ids: set[str]) -> int`](../../../cdm/workers/maintenance.py#L317)
- function: [`RetentionService._exists(self, job_id: str) -> bool`](../../../cdm/workers/maintenance.py#L345)
- function: [`RetentionService._delete_archives(self, pruned: list[PrunedJob]) -> int`](../../../cdm/workers/maintenance.py#L352)
- class: [`GovInfoRefreshScheduler()`](../../../cdm/workers/maintenance.py#L370)
- function: [`GovInfoRefreshScheduler.__init__(self, submitter: JobSubmitter, discovery: GovInfoDiscovery) -> None`](../../../cdm/workers/maintenance.py#L375)
- function: [`GovInfoRefreshScheduler.run(self, now: datetime) -> tuple[int, list[str]]`](../../../cdm/workers/maintenance.py#L383)
- field: [`GovInfoRefreshScheduler.run.queued: list[str]`](../../../cdm/workers/maintenance.py#L385)

## cdm/workers/planners.py

[Source](../../../cdm/workers/planners.py)

- function: [`congress_for_year(year: int) -> int`](../../../cdm/workers/planners.py#L18)
- function: [`_iso_utc(moment: datetime) -> str`](../../../cdm/workers/planners.py#L22)
- function: [`_parse_utc(value: str) -> datetime`](../../../cdm/workers/planners.py#L26)
- class: [`DailyIngestPlanner()`](../../../cdm/workers/planners.py#L31)
- function: [`DailyIngestPlanner.payload(self, today: date) -> IngestPayload`](../../../cdm/workers/planners.py#L42)
- class: [`CoverageGapPlanner()`](../../../cdm/workers/planners.py#L64)
- function: [`CoverageGapPlanner.__init__(self, store: JobStore, ledger: LedgerConfig) -> None`](../../../cdm/workers/planners.py#L78)
- function: [`CoverageGapPlanner.holes(self, intervals: list[tuple[datetime, datetime]], lookback_start: datetime, current: datetime) -> list[tuple[datetime, datetime]]`](../../../cdm/workers/planners.py#L82)
- field: [`CoverageGapPlanner.holes.holes: list[tuple[datetime, datetime]]`](../../../cdm/workers/planners.py#L100)
- function: [`CoverageGapPlanner.chunk(self, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]`](../../../cdm/workers/planners.py#L110)
- field: [`CoverageGapPlanner.chunk.chunks: list[tuple[datetime, datetime]]`](../../../cdm/workers/planners.py#L111)
- function: [`CoverageGapPlanner.payloads(self, now: datetime \| None=None) -> list[IngestPayload]`](../../../cdm/workers/planners.py#L118)
- field: [`CoverageGapPlanner.payloads.payloads: list[IngestPayload]`](../../../cdm/workers/planners.py#L123)
- function: [`CoverageGapPlanner._intervals(rows: list[CoverageRow]) -> list[tuple[datetime, datetime]]`](../../../cdm/workers/planners.py#L156)
- class: [`StaticRefreshPlanner()`](../../../cdm/workers/planners.py#L169)
- function: [`StaticRefreshPlanner.payloads(self, today: date) -> list[IngestPayload]`](../../../cdm/workers/planners.py#L178)
- field: [`StaticRefreshPlanner.payloads.payloads: list[IngestPayload]`](../../../cdm/workers/planners.py#L182)

## cdm/workers/results.py

[Source](../../../cdm/workers/results.py)

- class: [`JobResult(BaseModel)`](../../../cdm/workers/results.py#L15)
- field: [`JobResult.job_id: str \| None`](../../../cdm/workers/results.py#L20)
- field: [`JobResult.skipped: bool \| None`](../../../cdm/workers/results.py#L21)
- field: [`JobResult.status: str \| None`](../../../cdm/workers/results.py#L22)
- field: [`JobResult.cancelled: bool \| None`](../../../cdm/workers/results.py#L23)
- field: [`JobResult.deferred: bool \| None`](../../../cdm/workers/results.py#L24)
- field: [`JobResult.index_jobs: list[str] \| None`](../../../cdm/workers/results.py#L25)
- field: [`JobResult.resource: str \| None`](../../../cdm/workers/results.py#L26)
- field: [`JobResult.packages_dispatched: list[str] \| None`](../../../cdm/workers/results.py#L27)
- field: [`JobResult.batched_jobs: int \| None`](../../../cdm/workers/results.py#L28)
- class: [`RetryableTask(Protocol)`](../../../cdm/workers/results.py#L31)
- class: [`RetryableTask._Request(Protocol)`](../../../cdm/workers/results.py#L34)
- field: [`RetryableTask._Request.retries: int`](../../../cdm/workers/results.py#L35)
- field: [`RetryableTask.request: _Request`](../../../cdm/workers/results.py#L37)
- function: [`RetryableTask.retry(self, *, exc: BaseException, countdown: int, max_retries: int) -> BaseException`](../../../cdm/workers/results.py#L39)
- class: [`TaskRetrier()`](../../../cdm/workers/results.py#L48)
- function: [`TaskRetrier.__init__(self, store: JobStore, queues: QueueConfig, classifier: FailureClassifier) -> None`](../../../cdm/workers/results.py#L51)
- function: [`TaskRetrier.handle(self, task: RetryableTask, job_id: str, exc: Exception) -> NoReturn`](../../../cdm/workers/results.py#L61)
- class: [`SkippedClaim()`](../../../cdm/workers/results.py#L82)
- function: [`SkippedClaim.__init__(self, store: JobStore) -> None`](../../../cdm/workers/results.py#L85)
- function: [`SkippedClaim.result(self, job_id: str) -> JobResult`](../../../cdm/workers/results.py#L88)

## cdm/workers/runtime.py

[Source](../../../cdm/workers/runtime.py)

- class: [`WorkerContainer(Container)`](../../../cdm/workers/runtime.py#L80)
- function: [`WorkerContainer.graph_repair_capture(self) -> GraphRepairCapture`](../../../cdm/workers/runtime.py#L84)
- function: [`WorkerContainer.graph_repair_rehearsal(self, url: str) -> GraphRepairRehearsal`](../../../cdm/workers/runtime.py#L87)
- function: [`WorkerContainer.graph_source_repair(self, staging_url: str \| None=None) -> LiveGraphRepair`](../../../cdm/workers/runtime.py#L90)
- function: [`WorkerContainer.voting_graph_promotion(self) -> VotingGraphPromotion`](../../../cdm/workers/runtime.py#L99)
- function: [`WorkerContainer.topic_training_job(self, options: TopicTrainingOptions, report: Callable[[AnalysisProgress], None]) -> TopicTrainingJob`](../../../cdm/workers/runtime.py#L102)
- function: [`WorkerContainer.graph_build_job(self, report: Callable[[AnalysisProgress], None]) -> GraphBuildJob`](../../../cdm/workers/runtime.py#L143)
- function: [`WorkerContainer.perspective_build_job(self, request: PerspectiveRequest, report: Callable[[AnalysisProgress], None]) -> PerspectiveBuildJob`](../../../cdm/workers/runtime.py#L154)
- function: [`WorkerContainer.topic_model_reader(self) -> TopicModelReader`](../../../cdm/workers/runtime.py#L166)
- function: [`WorkerContainer.metasubject_override_store(self) -> MetasubjectOverrideStore`](../../../cdm/workers/runtime.py#L174)
- function: [`WorkerContainer.metasubject_repository(self) -> MetasubjectRepository`](../../../cdm/workers/runtime.py#L180)
- function: [`WorkerContainer.congress_corpus_reader(self) -> CongressCorpusReader`](../../../cdm/workers/runtime.py#L188)
- function: [`WorkerContainer.boilerplate_learner(self) -> BoilerplateLearner`](../../../cdm/workers/runtime.py#L199)
- function: [`WorkerContainer.perspective_builder(self, *, use_llm: bool, lexicon: BoilerplateLexicon) -> PerspectiveBuilder`](../../../cdm/workers/runtime.py#L206)
- function: [`WorkerContainer.perspective_runner(self, *, use_llm: bool) -> PerspectiveRunner`](../../../cdm/workers/runtime.py#L221)
- function: [`WorkerContainer.redis_client(self) -> Redis`](../../../cdm/workers/runtime.py#L231)
- function: [`WorkerContainer.analytics_runner(self) -> AnalyticsJobRunner`](../../../cdm/workers/runtime.py#L235)
- function: [`WorkerContainer.job_heartbeat(self) -> JobHeartbeat`](../../../cdm/workers/runtime.py#L244)
- function: [`WorkerContainer.failure_classifier(self) -> FailureClassifier`](../../../cdm/workers/runtime.py#L248)
- function: [`WorkerContainer.task_retrier(self) -> TaskRetrier`](../../../cdm/workers/runtime.py#L252)
- function: [`WorkerContainer.govinfo_session(self) -> requests.Session`](../../../cdm/workers/runtime.py#L256)
- function: [`WorkerContainer.govinfo_rate_limiter(self) -> TokenBucket`](../../../cdm/workers/runtime.py#L260)
- function: [`WorkerContainer.congress_rate_limiter(self) -> TokenBucket`](../../../cdm/workers/runtime.py#L266)
- function: [`WorkerContainer.bill_state_reader(self) -> IndexedBillStateReader`](../../../cdm/workers/runtime.py#L274)
- function: [`WorkerContainer.record_library(self) -> RecordLibrary`](../../../cdm/workers/runtime.py#L278)
- function: [`WorkerContainer.ingest_runner(self) -> IngestJobRunner`](../../../cdm/workers/runtime.py#L282)
- function: [`WorkerContainer.govinfo_package_runner(self) -> GovInfoPackageRunner`](../../../cdm/workers/runtime.py#L298)
- function: [`WorkerContainer.govinfo_batch_runner(self) -> GovInfoBatchRunner`](../../../cdm/workers/runtime.py#L310)
- function: [`WorkerContainer.reconciliation_runner(self) -> ReconciliationRunner`](../../../cdm/workers/runtime.py#L314)
- function: [`WorkerContainer.index_runner(self) -> IndexJobRunner`](../../../cdm/workers/runtime.py#L318)
- function: [`WorkerContainer.daily_ingest_planner(self) -> DailyIngestPlanner`](../../../cdm/workers/runtime.py#L328)
- function: [`WorkerContainer.coverage_gap_planner(self) -> CoverageGapPlanner`](../../../cdm/workers/runtime.py#L332)
- function: [`WorkerContainer.static_refresh_planner(self) -> StaticRefreshPlanner`](../../../cdm/workers/runtime.py#L336)
- function: [`WorkerContainer.queue_depth_probe(self) -> QueueDepthProbe`](../../../cdm/workers/runtime.py#L340)
- function: [`WorkerContainer.active_job_probe(self) -> ActiveJobProbe`](../../../cdm/workers/runtime.py#L344)
- function: [`WorkerContainer.recovery_service(self) -> JobRecoveryService`](../../../cdm/workers/runtime.py#L348)
- function: [`WorkerContainer.retention_service(self) -> RetentionService`](../../../cdm/workers/runtime.py#L360)
- function: [`WorkerContainer.govinfo_refresh_scheduler(self) -> GovInfoRefreshScheduler`](../../../cdm/workers/runtime.py#L369)

## cdm/workers/tasks.py

[Source](../../../cdm/workers/tasks.py)

- function: [`_container() -> WorkerContainer`](../../../cdm/workers/tasks.py#L29)
- function: [`warm_store(**_: object) -> None`](../../../cdm/workers/tasks.py#L34)
- function: [`_execute(task: object, job_id: str, run: Callable[[str], JobResult]) -> JsonObject`](../../../cdm/workers/tasks.py#L39)
- function: [`_retry(task: object, job_id: str, exc: Exception) -> NoReturn`](../../../cdm/workers/tasks.py#L48)
- function: [`run_ingest_job(self: object, job_id: str) -> JsonObject`](../../../cdm/workers/tasks.py#L58)
- function: [`run_govinfo_bulk_job(self: object, job_id: str) -> JsonObject`](../../../cdm/workers/tasks.py#L63)
- function: [`run_govinfo_bulk_batch(self: object, batch_id: str) -> JsonObject`](../../../cdm/workers/tasks.py#L69)
- function: [`run_index_job(self: object, job_id: str) -> JsonObject`](../../../cdm/workers/tasks.py#L75)
- function: [`run_reconciliation_job(self: object, job_id: str) -> JsonObject`](../../../cdm/workers/tasks.py#L80)
- function: [`run_analytics_job(self: object, job_id: str) -> JsonObject`](../../../cdm/workers/tasks.py#L91)
- function: [`schedule_daily_ingest() -> JsonObject`](../../../cdm/workers/tasks.py#L96)
- function: [`schedule_coverage_gaps() -> JsonObject`](../../../cdm/workers/tasks.py#L104)
- function: [`schedule_static_refresh() -> JsonObject`](../../../cdm/workers/tasks.py#L117)
- function: [`schedule_topic_training() -> JsonObject`](../../../cdm/workers/tasks.py#L129)
- function: [`schedule_member_graph_build() -> JsonObject`](../../../cdm/workers/tasks.py#L135)
- function: [`schedule_perspective_build() -> JsonObject`](../../../cdm/workers/tasks.py#L141)
- function: [`schedule_vote_refresh() -> JsonObject`](../../../cdm/workers/tasks.py#L151)
- function: [`schedule_govinfo_refresh() -> JsonObject`](../../../cdm/workers/tasks.py#L162)
- function: [`recover_failed_ingest_jobs() -> JsonObject`](../../../cdm/workers/tasks.py#L169)
- function: [`trim_logs() -> JsonObject`](../../../cdm/workers/tasks.py#L176)
- function: [`run_retention_maintenance() -> JsonObject`](../../../cdm/workers/tasks.py#L183)

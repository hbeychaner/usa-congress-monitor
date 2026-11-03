# topics source reference

[All source areas](README.md)

Generated from declarations; see the catalogue scope in the index.

## cdm/topics/__init__.py

[Source](../../../cdm/topics/__init__.py)

No declarations in this module.


## cdm/topics/retirement.py

[Source](../../../cdm/topics/retirement.py)

- class: [`ReferenceState(StrEnum)`](../../../cdm/topics/retirement.py#L17)
- class: [`ReferenceKind(StrEnum)`](../../../cdm/topics/retirement.py#L23)
- class: [`PublishedReference(BaseModel)`](../../../cdm/topics/retirement.py#L30)
- field: [`PublishedReference.kind: ReferenceKind`](../../../cdm/topics/retirement.py#L31)
- field: [`PublishedReference.model_version: str \| None`](../../../cdm/topics/retirement.py#L32)
- field: [`PublishedReference.congress: int \| None`](../../../cdm/topics/retirement.py#L33)
- class: [`_PerspectiveLineage(BaseModel)`](../../../cdm/topics/retirement.py#L36)
- field: [`_PerspectiveLineage.kind: PerspectiveKind`](../../../cdm/topics/retirement.py#L37)
- field: [`_PerspectiveLineage.congress: int`](../../../cdm/topics/retirement.py#L38)
- field: [`_PerspectiveLineage.model_version: str \| None`](../../../cdm/topics/retirement.py#L39)
- class: [`TopicRunReview(BaseModel)`](../../../cdm/topics/retirement.py#L42)
- field: [`TopicRunReview.run: CompletedTopicRun`](../../../cdm/topics/retirement.py#L43)
- field: [`TopicRunReview.state: ReferenceState`](../../../cdm/topics/retirement.py#L44)
- field: [`TopicRunReview.cache_state: ReferenceState`](../../../cdm/topics/retirement.py#L45)
- field: [`TopicRunReview.cache_shared_with: list[str]`](../../../cdm/topics/retirement.py#L46)
- class: [`RetirementReport(BaseModel)`](../../../cdm/topics/retirement.py#L49)
- field: [`RetirementReport.generated_at: AwareDatetime`](../../../cdm/topics/retirement.py#L50)
- field: [`RetirementReport.deletion_authorized: Literal[False]`](../../../cdm/topics/retirement.py#L51)
- field: [`RetirementReport.current_run: CompletedTopicRun \| None`](../../../cdm/topics/retirement.py#L52)
- field: [`RetirementReport.runs: list[TopicRunReview]`](../../../cdm/topics/retirement.py#L53)
- field: [`RetirementReport.references: list[PublishedReference]`](../../../cdm/topics/retirement.py#L54)
- field: [`RetirementReport.legacy_embedding_index: str`](../../../cdm/topics/retirement.py#L55)
- field: [`RetirementReport.unknown_cache_versions: list[str]`](../../../cdm/topics/retirement.py#L56)
- field: [`RetirementReport.warnings: list[str]`](../../../cdm/topics/retirement.py#L57)
- field: [`RetirementReport.limitations: tuple[str, ...]`](../../../cdm/topics/retirement.py#L58)
- class: [`RetirementReporter()`](../../../cdm/topics/retirement.py#L69)
- function: [`RetirementReporter.__init__(self, publications: TopicPublicationStore, graphs: GraphStore, legacy_embedding_index: str) -> None`](../../../cdm/topics/retirement.py#L70)
- function: [`RetirementReporter._inventory(self) -> tuple[list[CompletedTopicRun], list[_PerspectiveLineage]]`](../../../cdm/topics/retirement.py#L80)
- field: [`RetirementReporter._inventory.runs: list[CompletedTopicRun]`](../../../cdm/topics/retirement.py#L83)
- field: [`RetirementReporter._inventory.perspectives: list[_PerspectiveLineage]`](../../../cdm/topics/retirement.py#L84)
- function: [`RetirementReporter.report(self) -> RetirementReport`](../../../cdm/topics/retirement.py#L117)
- field: [`RetirementReporter.report.references: list[PublishedReference]`](../../../cdm/topics/retirement.py#L120)
- field: [`RetirementReporter.report.warnings: list[str]`](../../../cdm/topics/retirement.py#L121)
- field: [`RetirementReporter.report.reviews: list[TopicRunReview]`](../../../cdm/topics/retirement.py#L180)

## cdm/topics/training.py

[Source](../../../cdm/topics/training.py)

- class: [`TopicTrainingOutput(BaseModel)`](../../../cdm/topics/training.py#L50)
- field: [`TopicTrainingOutput.documents: list[TopicDocument]`](../../../cdm/topics/training.py#L51)
- field: [`TopicTrainingOutput.topics: list[TopicSummaryRow]`](../../../cdm/topics/training.py#L52)
- field: [`TopicTrainingOutput.assignments: list[TopicAssignment]`](../../../cdm/topics/training.py#L53)
- field: [`TopicTrainingOutput.over_time: list[TopicTimeBin]`](../../../cdm/topics/training.py#L54)
- field: [`TopicTrainingOutput.metasubjects: list[Metasubject]`](../../../cdm/topics/training.py#L55)
- field: [`TopicTrainingOutput.grouped_assignments: list[MetasubjectAssignment]`](../../../cdm/topics/training.py#L56)
- field: [`TopicTrainingOutput.metasubject_over_time: list[MetasubjectOverTimeRow]`](../../../cdm/topics/training.py#L57)
- function: [`TopicTrainingOutput.validate_coverage(self) -> Self`](../../../cdm/topics/training.py#L60)
- field: [`TopicTrainingOutput.validate_coverage.topic_totals: Counter[int]`](../../../cdm/topics/training.py#L125)
- field: [`TopicTrainingOutput.validate_coverage.group_totals: Counter[int]`](../../../cdm/topics/training.py#L126)
- function: [`TopicTrainingOutput.counts(self) -> TopicRunCounts`](../../../cdm/topics/training.py#L143)
- class: [`TopicTrainingJob()`](../../../cdm/topics/training.py#L153)
- function: [`TopicTrainingJob.__init__(self, client: Elasticsearch, publications: TopicPublicationStore, repository: MetasubjectRepository, modeler: TopicModeler, builder: MetasubjectBuilder, assigner_factory: Callable[[list[Metasubject]], MetasubjectAssigner], options: TopicTrainingOptions, report: Callable[[TrainingProgress], None], labeler: TopicLabeler \| None=None, progress: TrainingProgressConfig \| None=None) -> None`](../../../cdm/topics/training.py#L154)
- function: [`TopicTrainingJob._stage(self, stage: str, progress: float) -> None`](../../../cdm/topics/training.py#L179)
- function: [`TopicTrainingJob._fetch(self) -> list[TopicDocument]`](../../../cdm/topics/training.py#L182)
- field: [`TopicTrainingJob._fetch.collected: list[JsonObject]`](../../../cdm/topics/training.py#L211)
- function: [`TopicTrainingJob._embedding_progress(self, fraction: float) -> None`](../../../cdm/topics/training.py#L221)
- function: [`TopicTrainingJob._fit(self, documents: list[TopicDocument]) -> TopicTrainingOutput`](../../../cdm/topics/training.py#L230)
- function: [`TopicTrainingJob._actions(self, output: TopicTrainingOutput, run: TopicRunSpecification) -> Iterator[JsonObject]`](../../../cdm/topics/training.py#L294)
- function: [`TopicTrainingJob.execute(self) -> CompletedTopicRun \| None`](../../../cdm/topics/training.py#L344)

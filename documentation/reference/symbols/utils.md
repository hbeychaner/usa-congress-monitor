# utils source reference

[All source areas](README.md)

Generated from declarations; see the catalogue scope in the index.

## cdm/utils/__init__.py

[Source](../../../cdm/utils/__init__.py)

No declarations in this module.


## cdm/utils/archive_sweeper.py

[Source](../../../cdm/utils/archive_sweeper.py)

- class: [`SweepReport(BaseModel)`](../../../cdm/utils/archive_sweeper.py#L16)
- field: [`SweepReport.directories_removed: int`](../../../cdm/utils/archive_sweeper.py#L17)
- field: [`SweepReport.bytes_freed: int`](../../../cdm/utils/archive_sweeper.py#L18)
- class: [`OrphanArchiveSweeper()`](../../../cdm/utils/archive_sweeper.py#L21)
- function: [`OrphanArchiveSweeper.__init__(self, root: Path, name_prefix: str, min_age: timedelta=MIN_ORPHAN_AGE) -> None`](../../../cdm/utils/archive_sweeper.py#L24)
- function: [`OrphanArchiveSweeper._size(directory: Path) -> int`](../../../cdm/utils/archive_sweeper.py#L32)
- function: [`OrphanArchiveSweeper.sweep(self, known_ids: set[str]) -> SweepReport`](../../../cdm/utils/archive_sweeper.py#L42)

## cdm/utils/cached_embedder.py

[Source](../../../cdm/utils/cached_embedder.py)

- class: [`TextEmbedder(Protocol)`](../../../cdm/utils/cached_embedder.py#L16)
- function: [`TextEmbedder.get_sentence_embedding_dimension(self) -> int \| None`](../../../cdm/utils/cached_embedder.py#L17)
- function: [`TextEmbedder.encode(self, texts: list[str], show_progress_bar: bool=False) -> np.ndarray`](../../../cdm/utils/cached_embedder.py#L19)
- class: [`EmbeddingJob()`](../../../cdm/utils/cached_embedder.py#L27)
- field: [`EmbeddingJob.doc_id: str`](../../../cdm/utils/cached_embedder.py#L28)
- field: [`EmbeddingJob.text: str`](../../../cdm/utils/cached_embedder.py#L29)
- class: [`CachedEmbedder()`](../../../cdm/utils/cached_embedder.py#L32)
- function: [`CachedEmbedder.__init__(self, store: EmbeddingStore, embedder_factory: Callable[[], TextEmbedder], chunk_size: int=EMBED_CHUNK_SIZE) -> None`](../../../cdm/utils/cached_embedder.py#L35)
- function: [`CachedEmbedder.embed(self, jobs: Sequence[EmbeddingJob], on_progress: Callable[[float], None] \| None=None) -> np.ndarray`](../../../cdm/utils/cached_embedder.py#L45)
- function: [`CachedEmbedder._report(on_progress: Callable[[float], None] \| None, done: int, total: int) -> None`](../../../cdm/utils/cached_embedder.py#L85)

## cdm/utils/json_types.py

[Source](../../../cdm/utils/json_types.py)

No declarations in this module.


## cdm/utils/lemmatize.py

[Source](../../../cdm/utils/lemmatize.py)

- class: [`LanguageLoader(Protocol)`](../../../cdm/utils/lemmatize.py#L16)
- function: [`LanguageLoader.__call__(self, name: str, *, exclude: Iterable[str]) -> Language`](../../../cdm/utils/lemmatize.py#L17)
- class: [`SpacyLemmatizer()`](../../../cdm/utils/lemmatize.py#L20)
- function: [`SpacyLemmatizer.__init__(self, settings: LemmatizationConfig, loader: LanguageLoader, logger: logging.Logger) -> None`](../../../cdm/utils/lemmatize.py#L21)
- function: [`SpacyLemmatizer._model(self) -> Language`](../../../cdm/utils/lemmatize.py#L31)
- function: [`SpacyLemmatizer.lemmatize(self, texts: Sequence[str]) -> list[str]`](../../../cdm/utils/lemmatize.py#L46)
- function: [`SpacyLemmatizer.warm(self) -> None`](../../../cdm/utils/lemmatize.py#L67)
- function: [`SpacyLemmatizer.try_query(self, text: str) -> str`](../../../cdm/utils/lemmatize.py#L72)
- field: [`_default_lemmatizer: SpacyLemmatizer`](../../../cdm/utils/lemmatize.py#L82)
- function: [`lemmatize_texts(texts: Sequence[str]) -> list[str]`](../../../cdm/utils/lemmatize.py#L87)
- function: [`lemmatize_text(text: str) -> str`](../../../cdm/utils/lemmatize.py#L91)
- function: [`try_lemmatize_query(text: str) -> str`](../../../cdm/utils/lemmatize.py#L95)
- function: [`warm_lemmatizer() -> None`](../../../cdm/utils/lemmatize.py#L99)

## cdm/utils/log_trimmer.py

[Source](../../../cdm/utils/log_trimmer.py)

- class: [`TrimResult(BaseModel)`](../../../cdm/utils/log_trimmer.py#L15)
- field: [`TrimResult.path: str`](../../../cdm/utils/log_trimmer.py#L16)
- field: [`TrimResult.bytes_before: int`](../../../cdm/utils/log_trimmer.py#L17)
- field: [`TrimResult.bytes_after: int`](../../../cdm/utils/log_trimmer.py#L18)
- class: [`LogTrimmer()`](../../../cdm/utils/log_trimmer.py#L21)
- function: [`LogTrimmer.__init__(self, directory: Path=LOG_DIRECTORY, max_lines: int=MAX_LOG_LINES) -> None`](../../../cdm/utils/log_trimmer.py#L24)
- function: [`LogTrimmer._tail(self, path: Path) -> bytes \| None`](../../../cdm/utils/log_trimmer.py#L30)
- field: [`LogTrimmer._tail.blocks: list[bytes]`](../../../cdm/utils/log_trimmer.py#L32)
- function: [`LogTrimmer.trim(self, path: Path) -> TrimResult \| None`](../../../cdm/utils/log_trimmer.py#L56)
- function: [`LogTrimmer.trim_all(self) -> list[TrimResult]`](../../../cdm/utils/log_trimmer.py#L66)

## cdm/utils/logger.py

[Source](../../../cdm/utils/logger.py)

- field: [`_state: dict`](../../../cdm/utils/logger.py#L10)
- function: [`configure_logging(level: str \| None=None) -> None`](../../../cdm/utils/logger.py#L13)
- field: [`configure_logging.q: queue.Queue`](../../../cdm/utils/logger.py#L31)
- function: [`get_logger(name: str) -> logging.Logger`](../../../cdm/utils/logger.py#L46)

## cdm/utils/metasubject_namer.py

[Source](../../../cdm/utils/metasubject_namer.py)

- class: [`MetasubjectLabelConfig(BaseModel)`](../../../cdm/utils/metasubject_namer.py#L17)
- field: [`MetasubjectLabelConfig.prompt_topics: int`](../../../cdm/utils/metasubject_namer.py#L18)
- field: [`MetasubjectLabelConfig.max_words: int`](../../../cdm/utils/metasubject_namer.py#L19)
- field: [`MetasubjectLabelConfig.example_topics: int`](../../../cdm/utils/metasubject_namer.py#L20)
- field: [`MetasubjectLabelConfig.attempts: int`](../../../cdm/utils/metasubject_namer.py#L21)
- field: [`MetasubjectLabelConfig.system_prompt: str`](../../../cdm/utils/metasubject_namer.py#L22)
- field: [`MetasubjectLabelConfig.rename_prompt: str`](../../../cdm/utils/metasubject_namer.py#L29)
- class: [`OllamaMetasubjectNamer()`](../../../cdm/utils/metasubject_namer.py#L40)
- function: [`OllamaMetasubjectNamer.__init__(self, ollama: OllamaClient, config: MetasubjectLabelConfig \| None=None) -> None`](../../../cdm/utils/metasubject_namer.py#L43)
- function: [`OllamaMetasubjectNamer.name(self, members: Sequence[TopicVector]) -> LabelResult`](../../../cdm/utils/metasubject_namer.py#L50)
- class: [`OllamaNameDisambiguator()`](../../../cdm/utils/metasubject_namer.py#L64)
- function: [`OllamaNameDisambiguator.__init__(self, ollama: OllamaClient, config: MetasubjectLabelConfig \| None=None) -> None`](../../../cdm/utils/metasubject_namer.py#L67)
- function: [`OllamaNameDisambiguator.rename(self, colliding: Sequence[NamedGroup], taken: set[str]) -> dict[int, LabelResult]`](../../../cdm/utils/metasubject_namer.py#L73)
- field: [`OllamaNameDisambiguator.rename.renamed: dict[int, LabelResult]`](../../../cdm/utils/metasubject_namer.py#L77)
- function: [`OllamaNameDisambiguator._titles(self, group: NamedGroup) -> str`](../../../cdm/utils/metasubject_namer.py#L85)
- function: [`OllamaNameDisambiguator._name_for(self, group: NamedGroup, others: Sequence[NamedGroup], used: set[str]) -> LabelResult`](../../../cdm/utils/metasubject_namer.py#L91)

## cdm/utils/metasubjects.py

[Source](../../../cdm/utils/metasubjects.py)

- class: [`TopicVector(BaseModel)`](../../../cdm/utils/metasubjects.py#L28)
- field: [`TopicVector.topic_id: int`](../../../cdm/utils/metasubjects.py#L33)
- field: [`TopicVector.size: int`](../../../cdm/utils/metasubjects.py#L34)
- field: [`TopicVector.label: str`](../../../cdm/utils/metasubjects.py#L35)
- field: [`TopicVector.top_words: list[str]`](../../../cdm/utils/metasubjects.py#L36)
- field: [`TopicVector.vector: np.ndarray`](../../../cdm/utils/metasubjects.py#L37)
- class: [`Metasubject(LabelProvenance)`](../../../cdm/utils/metasubjects.py#L40)
- field: [`Metasubject.metasubject_id: int`](../../../cdm/utils/metasubjects.py#L41)
- field: [`Metasubject.name: str`](../../../cdm/utils/metasubjects.py#L42)
- field: [`Metasubject.topic_ids: list[int]`](../../../cdm/utils/metasubjects.py#L43)
- field: [`Metasubject.size: int`](../../../cdm/utils/metasubjects.py#L44)
- field: [`Metasubject.top_words: list[str]`](../../../cdm/utils/metasubjects.py#L45)
- field: [`Metasubject.centroid: list[float]`](../../../cdm/utils/metasubjects.py#L46)
- class: [`MetasubjectOverTimeRow(BaseModel)`](../../../cdm/utils/metasubjects.py#L49)
- field: [`MetasubjectOverTimeRow.metasubject_id: int`](../../../cdm/utils/metasubjects.py#L50)
- field: [`MetasubjectOverTimeRow.frequency: int`](../../../cdm/utils/metasubjects.py#L51)
- field: [`MetasubjectOverTimeRow.timestamp: str`](../../../cdm/utils/metasubjects.py#L52)
- class: [`MetasubjectNamer(Protocol)`](../../../cdm/utils/metasubjects.py#L55)
- function: [`MetasubjectNamer.name(self, members: Sequence[TopicVector]) -> LabelResult`](../../../cdm/utils/metasubjects.py#L56)
- class: [`NamedGroup(BaseModel)`](../../../cdm/utils/metasubjects.py#L59)
- field: [`NamedGroup.metasubject_id: int`](../../../cdm/utils/metasubjects.py#L64)
- field: [`NamedGroup.name: str`](../../../cdm/utils/metasubjects.py#L65)
- field: [`NamedGroup.members: list[TopicVector]`](../../../cdm/utils/metasubjects.py#L66)
- class: [`NameDisambiguator(Protocol)`](../../../cdm/utils/metasubjects.py#L69)
- function: [`NameDisambiguator.rename(self, colliding: Sequence[NamedGroup], taken: set[str]) -> dict[int, LabelResult]`](../../../cdm/utils/metasubjects.py#L70)
- class: [`MetasubjectOverrides(BaseModel)`](../../../cdm/utils/metasubjects.py#L77)
- field: [`MetasubjectOverrides.names: dict[int, str]`](../../../cdm/utils/metasubjects.py#L80)
- class: [`AssignedBy(StrEnum)`](../../../cdm/utils/metasubjects.py#L83)
- class: [`MetasubjectAssignment(BaseModel)`](../../../cdm/utils/metasubjects.py#L88)
- field: [`MetasubjectAssignment.doc_id: str`](../../../cdm/utils/metasubjects.py#L89)
- field: [`MetasubjectAssignment.metasubject_id: int`](../../../cdm/utils/metasubjects.py#L90)
- field: [`MetasubjectAssignment.confidence: float`](../../../cdm/utils/metasubjects.py#L91)
- field: [`MetasubjectAssignment.assigned_by: AssignedBy`](../../../cdm/utils/metasubjects.py#L92)
- field: [`MetasubjectAssignment.low_confidence: bool`](../../../cdm/utils/metasubjects.py#L93)
- class: [`LargestTopicNamer()`](../../../cdm/utils/metasubjects.py#L96)
- function: [`LargestTopicNamer.name(self, members: Sequence[TopicVector]) -> LabelResult`](../../../cdm/utils/metasubjects.py#L99)
- function: [`_unit(vector: np.ndarray) -> np.ndarray`](../../../cdm/utils/metasubjects.py#L107)
- class: [`StableIdMatcher()`](../../../cdm/utils/metasubjects.py#L112)
- function: [`StableIdMatcher.__init__(self, min_similarity: float) -> None`](../../../cdm/utils/metasubjects.py#L115)
- function: [`StableIdMatcher.match(self, centroids: Sequence[np.ndarray], previous: Sequence[Metasubject]) -> list[Metasubject \| None]`](../../../cdm/utils/metasubjects.py#L118)
- field: [`StableIdMatcher.match.matches: list[Metasubject \| None]`](../../../cdm/utils/metasubjects.py#L122)
- class: [`MetasubjectBuilder()`](../../../cdm/utils/metasubjects.py#L134)
- function: [`MetasubjectBuilder.__init__(self, namer: MetasubjectNamer, matcher: StableIdMatcher, target_groups: int, overrides: MetasubjectOverrides \| None=None, disambiguator: NameDisambiguator \| None=None, name_carry_max_size_ratio: float \| None=None) -> None`](../../../cdm/utils/metasubjects.py#L137)
- function: [`MetasubjectBuilder._cluster(self, topics: Sequence[TopicVector]) -> list[list[TopicVector]]`](../../../cdm/utils/metasubjects.py#L153)
- field: [`MetasubjectBuilder._cluster.groups: dict[int, list[TopicVector]]`](../../../cdm/utils/metasubjects.py#L161)
- function: [`MetasubjectBuilder._centroid(members: Sequence[TopicVector]) -> np.ndarray`](../../../cdm/utils/metasubjects.py#L167)
- function: [`MetasubjectBuilder._keeps_name(self, match: Metasubject, size: int) -> bool`](../../../cdm/utils/metasubjects.py#L172)
- function: [`MetasubjectBuilder.build(self, topics: Sequence[TopicVector], previous: Sequence[Metasubject]=()) -> list[Metasubject]`](../../../cdm/utils/metasubjects.py#L179)
- field: [`MetasubjectBuilder.build.results: list[Metasubject]`](../../../cdm/utils/metasubjects.py#L189)
- field: [`MetasubjectBuilder.build.members_of: dict[int, list[TopicVector]]`](../../../cdm/utils/metasubjects.py#L190)
- function: [`MetasubjectBuilder._resolve_duplicates(self, results: list[Metasubject], members_of: dict[int, list[TopicVector]]) -> None`](../../../cdm/utils/metasubjects.py#L229)
- field: [`MetasubjectBuilder._resolve_duplicates.by_name: dict[str, list[Metasubject]]`](../../../cdm/utils/metasubjects.py#L235)
- function: [`topic_to_metasubject(metasubjects: Sequence[Metasubject]) -> dict[int, int]`](../../../cdm/utils/metasubjects.py#L264)
- class: [`MetasubjectAssigner()`](../../../cdm/utils/metasubjects.py#L272)
- function: [`MetasubjectAssigner.__init__(self, metasubjects: Sequence[Metasubject], low_confidence_below: float) -> None`](../../../cdm/utils/metasubjects.py#L275)
- function: [`MetasubjectAssigner.assign(self, doc_ids: Sequence[str], topic_ids: Sequence[int], embeddings: np.ndarray) -> list[MetasubjectAssignment]`](../../../cdm/utils/metasubjects.py#L288)
- field: [`MetasubjectAssigner.assign.results: list[MetasubjectAssignment]`](../../../cdm/utils/metasubjects.py#L300)
- function: [`MetasubjectAssigner.with_sizes(self, assignments: Sequence[MetasubjectAssignment]) -> list[Metasubject]`](../../../cdm/utils/metasubjects.py#L319)
- field: [`MetasubjectAssigner.with_sizes.counts: dict[int, int]`](../../../cdm/utils/metasubjects.py#L323)
- class: [`QuarterlyTrendBuilder()`](../../../cdm/utils/metasubjects.py#L336)
- function: [`QuarterlyTrendBuilder._quarter_start(moment: datetime) -> str`](../../../cdm/utils/metasubjects.py#L340)
- function: [`QuarterlyTrendBuilder.build(self, assignments: Sequence[MetasubjectAssignment], timestamps: Sequence[datetime \| None]) -> list[MetasubjectOverTimeRow]`](../../../cdm/utils/metasubjects.py#L344)
- field: [`QuarterlyTrendBuilder.build.totals: dict[tuple[int, str], int]`](../../../cdm/utils/metasubjects.py#L349)

## cdm/utils/ollama_client.py

[Source](../../../cdm/utils/ollama_client.py)

- class: [`OllamaRole(StrEnum)`](../../../cdm/utils/ollama_client.py#L17)
- class: [`OllamaChatMessage(BaseModel)`](../../../cdm/utils/ollama_client.py#L22)
- field: [`OllamaChatMessage.role: OllamaRole`](../../../cdm/utils/ollama_client.py#L23)
- field: [`OllamaChatMessage.content: str`](../../../cdm/utils/ollama_client.py#L24)
- class: [`OllamaOptions(BaseModel)`](../../../cdm/utils/ollama_client.py#L27)
- field: [`OllamaOptions.temperature: float`](../../../cdm/utils/ollama_client.py#L28)
- class: [`OllamaRequest(BaseModel)`](../../../cdm/utils/ollama_client.py#L31)
- field: [`OllamaRequest.model: str`](../../../cdm/utils/ollama_client.py#L32)
- field: [`OllamaRequest.stream: bool`](../../../cdm/utils/ollama_client.py#L33)
- field: [`OllamaRequest.options: OllamaOptions`](../../../cdm/utils/ollama_client.py#L34)
- field: [`OllamaRequest.messages: list[OllamaChatMessage]`](../../../cdm/utils/ollama_client.py#L35)
- class: [`OllamaMessage(BaseModel)`](../../../cdm/utils/ollama_client.py#L38)
- field: [`OllamaMessage.content: str`](../../../cdm/utils/ollama_client.py#L39)
- class: [`OllamaReply(BaseModel)`](../../../cdm/utils/ollama_client.py#L42)
- field: [`OllamaReply.content: str`](../../../cdm/utils/ollama_client.py#L43)
- field: [`OllamaReply.fallback_reason: LabelFallbackReason \| None`](../../../cdm/utils/ollama_client.py#L44)
- class: [`OllamaClient()`](../../../cdm/utils/ollama_client.py#L47)
- function: [`OllamaClient.__init__(self, config: OllamaConfig) -> None`](../../../cdm/utils/ollama_client.py#L48)
- function: [`OllamaClient.is_available(self) -> bool`](../../../cdm/utils/ollama_client.py#L51)
- function: [`OllamaClient.chat(self, system: str, user: str) -> OllamaReply`](../../../cdm/utils/ollama_client.py#L61)
- function: [`OllamaClient.label(self, system: str, user: str, fallback: LabelResult, *, max_words: int, strip_prefix: bool=True) -> LabelResult`](../../../cdm/utils/ollama_client.py#L92)

## cdm/utils/rate_limiter.py

[Source](../../../cdm/utils/rate_limiter.py)

- class: [`TokenBucket()`](../../../cdm/utils/rate_limiter.py#L26)
- function: [`TokenBucket.__init__(self, rate_per_hour: float=4800.0) -> None`](../../../cdm/utils/rate_limiter.py#L36)
- function: [`TokenBucket.acquire(self) -> None`](../../../cdm/utils/rate_limiter.py#L44)
- function: [`TokenBucket.rate_per_hour(self) -> float`](../../../cdm/utils/rate_limiter.py#L63)
- class: [`SharedTokenBucket(TokenBucket)`](../../../cdm/utils/rate_limiter.py#L67)
- function: [`SharedTokenBucket.__init__(self, redis_client: Redis, key: str, rate_per_hour: float=4800.0) -> None`](../../../cdm/utils/rate_limiter.py#L89)
- function: [`SharedTokenBucket.acquire(self) -> None`](../../../cdm/utils/rate_limiter.py#L96)

## cdm/utils/topic_labeler.py

[Source](../../../cdm/utils/topic_labeler.py)

- class: [`TopicLabelConfig(BaseModel)`](../../../cdm/utils/topic_labeler.py#L23)
- field: [`TopicLabelConfig.system_prompt: str`](../../../cdm/utils/topic_labeler.py#L24)
- field: [`TopicLabelConfig.prompt_keywords: int`](../../../cdm/utils/topic_labeler.py#L35)
- field: [`TopicLabelConfig.prompt_samples: int`](../../../cdm/utils/topic_labeler.py#L36)
- field: [`TopicLabelConfig.sample_chars: int`](../../../cdm/utils/topic_labeler.py#L37)
- field: [`TopicLabelConfig.max_words: int`](../../../cdm/utils/topic_labeler.py#L38)
- class: [`TopicLabeler()`](../../../cdm/utils/topic_labeler.py#L41)
- function: [`TopicLabeler.__init__(self, ollama: OllamaClient, config: TopicLabelConfig \| None=None) -> None`](../../../cdm/utils/topic_labeler.py#L44)
- function: [`TopicLabeler.generate(self, top_words: list[str], representative_docs: list[str], *, fallback_label: str='General') -> LabelResult`](../../../cdm/utils/topic_labeler.py#L50)
- function: [`TopicLabeler.label_topics(self, summaries: list[TopicSummaryRow], representative_docs: dict[int, list[str]]) -> dict[int, LabelResult]`](../../../cdm/utils/topic_labeler.py#L75)
- field: [`TopicLabeler.label_topics.labels: dict[int, LabelResult]`](../../../cdm/utils/topic_labeler.py#L84)

## cdm/utils/topic_modeler.py

[Source](../../../cdm/utils/topic_modeler.py)

- class: [`TopicDocument()`](../../../cdm/utils/topic_modeler.py#L90)
- field: [`TopicDocument.doc_id: str`](../../../cdm/utils/topic_modeler.py#L99)
- field: [`TopicDocument.text: str`](../../../cdm/utils/topic_modeler.py#L100)
- field: [`TopicDocument.timestamp: datetime \| None`](../../../cdm/utils/topic_modeler.py#L101)
- field: [`TopicDocument.embed_text: str`](../../../cdm/utils/topic_modeler.py#L102)
- function: [`TopicDocument.embedding_input(self) -> str`](../../../cdm/utils/topic_modeler.py#L105)
- class: [`TopicAssignment()`](../../../cdm/utils/topic_modeler.py#L110)
- field: [`TopicAssignment.doc_id: str`](../../../cdm/utils/topic_modeler.py#L111)
- field: [`TopicAssignment.topic_id: int`](../../../cdm/utils/topic_modeler.py#L112)
- field: [`TopicAssignment.probability: float`](../../../cdm/utils/topic_modeler.py#L113)
- function: [`_clean(text: str) -> str`](../../../cdm/utils/topic_modeler.py#L116)
- function: [`_parse_date(value: Any) -> datetime \| None`](../../../cdm/utils/topic_modeler.py#L120)
- function: [`_latest_summary_text(source: dict[str, Any]) -> tuple[str, str]`](../../../cdm/utils/topic_modeler.py#L129)
- function: [`_join(first: str, second: str) -> str`](../../../cdm/utils/topic_modeler.py#L144)
- function: [`_subject_terms(source: dict[str, Any]) -> str`](../../../cdm/utils/topic_modeler.py#L148)
- field: [`_subject_terms.terms: list[str]`](../../../cdm/utils/topic_modeler.py#L150)
- function: [`build_topic_documents(hits: list[dict[str, Any]]) -> list[TopicDocument]`](../../../cdm/utils/topic_modeler.py#L162)
- class: [`TopicModeler()`](../../../cdm/utils/topic_modeler.py#L200)
- function: [`TopicModeler.__init__(self, *, embedding_model: str='all-mpnet-base-v2', min_topic_size: int=25, nr_topics: int \| str \| None=None, embedding_store: EmbeddingStore \| None=None) -> None`](../../../cdm/utils/topic_modeler.py#L203)
- function: [`TopicModeler._embedder(self) -> Any`](../../../cdm/utils/topic_modeler.py#L221)
- function: [`TopicModeler._embed(self, documents: list[TopicDocument], on_progress: Callable[[float], None] \| None) -> np.ndarray`](../../../cdm/utils/topic_modeler.py#L226)
- function: [`TopicModeler.fit(self, documents: list[TopicDocument], on_embed_progress: Callable[[float], None] \| None=None) -> list[TopicAssignment]`](../../../cdm/utils/topic_modeler.py#L248)
- function: [`TopicModeler.transform(self, documents: list[TopicDocument]) -> list[TopicAssignment]`](../../../cdm/utils/topic_modeler.py#L282)
- function: [`TopicModeler.topics_over_time(self, *, nr_bins: int=60) -> list[TopicTimeBin]`](../../../cdm/utils/topic_modeler.py#L291)
- function: [`TopicModeler.topic_summaries(self) -> list[TopicSummaryRow]`](../../../cdm/utils/topic_modeler.py#L317)
- field: [`TopicModeler.topic_summaries.summaries: list[TopicSummaryRow]`](../../../cdm/utils/topic_modeler.py#L321)
- function: [`TopicModeler.document_embeddings(self) -> np.ndarray`](../../../cdm/utils/topic_modeler.py#L337)
- function: [`TopicModeler.topic_vectors(self, summaries: list[TopicSummaryRow]) -> list[TopicVector]`](../../../cdm/utils/topic_modeler.py#L346)
- function: [`TopicModeler.representative_docs(self) -> dict[int, list[str]]`](../../../cdm/utils/topic_modeler.py#L365)
- function: [`TopicModeler.save(self, path: Path \| str) -> None`](../../../cdm/utils/topic_modeler.py#L371)
- function: [`TopicModeler.load(cls, path: Path \| str, **kwargs: Any) -> TopicModeler`](../../../cdm/utils/topic_modeler.py#L382)
- function: [`TopicModeler._require_model(self) -> None`](../../../cdm/utils/topic_modeler.py#L387)
- function: [`_assignments(documents: list[TopicDocument], topics: Any, probabilities: Any) -> list[TopicAssignment]`](../../../cdm/utils/topic_modeler.py#L392)

## cdm/utils/topic_records.py

[Source](../../../cdm/utils/topic_records.py)

- class: [`TopicSummaryRow(LabelProvenance)`](../../../cdm/utils/topic_records.py#L10)
- field: [`TopicSummaryRow.topic_id: int`](../../../cdm/utils/topic_records.py#L11)
- field: [`TopicSummaryRow.name: str`](../../../cdm/utils/topic_records.py#L12)
- field: [`TopicSummaryRow.size: int`](../../../cdm/utils/topic_records.py#L13)
- field: [`TopicSummaryRow.top_words: list[str]`](../../../cdm/utils/topic_records.py#L14)
- field: [`TopicSummaryRow.label: str \| None`](../../../cdm/utils/topic_records.py#L15)
- field: [`TopicSummaryRow.metasubject_id: int \| None`](../../../cdm/utils/topic_records.py#L16)
- field: [`TopicSummaryRow.centroid: list[float] \| None`](../../../cdm/utils/topic_records.py#L17)
- class: [`TopicTimeBin(BaseModel)`](../../../cdm/utils/topic_records.py#L20)
- field: [`TopicTimeBin.topic_id: int`](../../../cdm/utils/topic_records.py#L21)
- field: [`TopicTimeBin.words: str`](../../../cdm/utils/topic_records.py#L22)
- field: [`TopicTimeBin.frequency: int`](../../../cdm/utils/topic_records.py#L23)
- field: [`TopicTimeBin.timestamp: str`](../../../cdm/utils/topic_records.py#L24)

## cdm/utils/topic_terms.py

[Source](../../../cdm/utils/topic_terms.py)

- function: [`topic_label(name: str \| None, topic_id: int) -> str`](../../../cdm/utils/topic_terms.py#L10)
- function: [`dedupe_terms(terms: Iterable[str]) -> list[str]`](../../../cdm/utils/topic_terms.py#L22)
- function: [`keyword_label(terms: Iterable[str], limit: int=4) -> str`](../../../cdm/utils/topic_terms.py#L38)
- field: [`keyword_label.seen: set[str]`](../../../cdm/utils/topic_terms.py#L40)
- field: [`keyword_label.parts: list[str]`](../../../cdm/utils/topic_terms.py#L41)

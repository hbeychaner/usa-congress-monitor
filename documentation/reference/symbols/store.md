# store source reference

[All source areas](README.md)

Generated from declarations; see the catalogue scope in the index.

## cdm/store/__init__.py

[Source](../../../cdm/store/__init__.py)

No declarations in this module.


## cdm/store/batch_indexing.py

[Source](../../../cdm/store/batch_indexing.py)

- class: [`IndexOutcome(BaseModel)`](../../../cdm/store/batch_indexing.py#L19)
- field: [`IndexOutcome.stream: str`](../../../cdm/store/batch_indexing.py#L20)
- field: [`IndexOutcome.resource: str`](../../../cdm/store/batch_indexing.py#L21)
- field: [`IndexOutcome.indexed: int`](../../../cdm/store/batch_indexing.py#L22)
- field: [`IndexOutcome.batches: int`](../../../cdm/store/batch_indexing.py#L23)
- field: [`IndexOutcome.pending: int`](../../../cdm/store/batch_indexing.py#L24)
- field: [`IndexOutcome.stream_length: int`](../../../cdm/store/batch_indexing.py#L25)
- field: [`IndexOutcome.status: str`](../../../cdm/store/batch_indexing.py#L26)
- field: [`IndexOutcome.replayed_from_archive: int \| None`](../../../cdm/store/batch_indexing.py#L27)
- class: [`StreamIndexer()`](../../../cdm/store/batch_indexing.py#L30)
- function: [`StreamIndexer.__init__(self, redis_client: Redis, opensearch_client: Elasticsearch, *, batch_docs: int, default_group: str) -> None`](../../../cdm/store/batch_indexing.py#L38)
- function: [`StreamIndexer.group(self, payload: IndexPayload) -> str`](../../../cdm/store/batch_indexing.py#L51)
- function: [`StreamIndexer.index(self, payloads: dict[str, IndexPayload], *, resource: str, target_index: str \| None, replace: bool, preserve_raw: bool) -> dict[str, IndexOutcome \| Exception]`](../../../cdm/store/batch_indexing.py#L54)
- class: [`_IndexRun()`](../../../cdm/store/batch_indexing.py#L68)
- function: [`_IndexRun.__init__(self, owner: StreamIndexer, payloads: dict[str, IndexPayload], resource: str, target_index: str \| None, replace: bool, preserve_raw: bool) -> None`](../../../cdm/store/batch_indexing.py#L71)
- function: [`_IndexRun.execute(self) -> dict[str, IndexOutcome \| Exception]`](../../../cdm/store/batch_indexing.py#L95)
- function: [`_IndexRun._drain(self, job_id: str, payload: IndexPayload, consumer: str) -> None`](../../../cdm/store/batch_indexing.py#L102)
- function: [`_IndexRun._document(self, entry: StreamEntry) -> dict[str, object]`](../../../cdm/store/batch_indexing.py#L118)
- function: [`_IndexRun._flush(self) -> None`](../../../cdm/store/batch_indexing.py#L128)
- field: [`_IndexRun._flush.acked: dict[str, list[str]]`](../../../cdm/store/batch_indexing.py#L145)
- function: [`_IndexRun._outcome(self, job_id: str) -> IndexOutcome \| Exception`](../../../cdm/store/batch_indexing.py#L155)

## cdm/store/client.py

[Source](../../../cdm/store/client.py)

- class: [`SearchConfigurationError(ValueError)`](../../../cdm/store/client.py#L12)
- class: [`IncompleteSearchError(RuntimeError)`](../../../cdm/store/client.py#L16)
- class: [`SearchCompletion(BaseModel)`](../../../cdm/store/client.py#L20)
- field: [`SearchCompletion.timed_out: bool`](../../../cdm/store/client.py#L21)
- field: [`SearchCompletion.failed_shards: int`](../../../cdm/store/client.py#L22)
- function: [`SearchCompletion.require_complete(self) -> None`](../../../cdm/store/client.py#L24)
- class: [`ElasticClientFactory()`](../../../cdm/store/client.py#L29)
- function: [`ElasticClientFactory.__init__(self, config: ElasticConfig) -> None`](../../../cdm/store/client.py#L32)
- function: [`ElasticClientFactory.create(self, *, url: str \| None=None, api_key: str \| None=None) -> Elasticsearch`](../../../cdm/store/client.py#L35)
- function: [`get_opensearch_client(*, url: str \| None=None, api_key: str \| None=None) -> Elasticsearch`](../../../cdm/store/client.py#L52)
- function: [`check_opensearch_connection(client: Elasticsearch) -> JsonObject`](../../../cdm/store/client.py#L59)

## cdm/store/embedding_store.py

[Source](../../../cdm/store/embedding_store.py)

- class: [`EmbeddingField(StrEnum)`](../../../cdm/store/embedding_store.py#L21)
- class: [`EmbeddingRecord(BaseModel)`](../../../cdm/store/embedding_store.py#L28)
- field: [`EmbeddingRecord.doc_id: str`](../../../cdm/store/embedding_store.py#L31)
- field: [`EmbeddingRecord.model: str`](../../../cdm/store/embedding_store.py#L32)
- field: [`EmbeddingRecord.content_hash: str`](../../../cdm/store/embedding_store.py#L33)
- field: [`EmbeddingRecord.embedding: list[float]`](../../../cdm/store/embedding_store.py#L34)
- field: [`EmbeddingRecord.embedded_at: datetime`](../../../cdm/store/embedding_store.py#L35)
- class: [`SimilarDocument(BaseModel)`](../../../cdm/store/embedding_store.py#L38)
- field: [`SimilarDocument.doc_id: str`](../../../cdm/store/embedding_store.py#L39)
- field: [`SimilarDocument.score: float`](../../../cdm/store/embedding_store.py#L40)
- class: [`EmbeddingNeighbors(BaseModel)`](../../../cdm/store/embedding_store.py#L43)
- field: [`EmbeddingNeighbors.source_found: bool`](../../../cdm/store/embedding_store.py#L44)
- field: [`EmbeddingNeighbors.neighbors: list[SimilarDocument]`](../../../cdm/store/embedding_store.py#L45)
- class: [`EmbeddingStore()`](../../../cdm/store/embedding_store.py#L48)
- function: [`EmbeddingStore.__init__(self, client: Elasticsearch, model: str, *, index: str, batch_docs: int, settings: EmbeddingSearchConfig \| None=None) -> None`](../../../cdm/store/embedding_store.py#L51)
- function: [`EmbeddingStore.content_hash(self, text: str) -> str`](../../../cdm/store/embedding_store.py#L66)
- function: [`EmbeddingStore.namespace(base_index: str, model: str) -> str`](../../../cdm/store/embedding_store.py#L72)
- function: [`EmbeddingStore.ensure_index(self, dims: int) -> None`](../../../cdm/store/embedding_store.py#L75)
- function: [`EmbeddingStore.fetch_fresh(self, expected: dict[str, str]) -> dict[str, np.ndarray]`](../../../cdm/store/embedding_store.py#L86)
- field: [`EmbeddingStore.fetch_fresh.fresh: dict[str, np.ndarray]`](../../../cdm/store/embedding_store.py#L88)
- function: [`EmbeddingStore.save(self, records: Iterable[EmbeddingRecord]) -> None`](../../../cdm/store/embedding_store.py#L116)
- function: [`EmbeddingStore.save.actions() -> Iterator[JsonObject]`](../../../cdm/store/embedding_store.py#L117)
- function: [`EmbeddingStore.similar(self, doc_id: str, size: int, *, cache: EmbeddingCache \| None=None, model: str \| None=None) -> EmbeddingNeighbors`](../../../cdm/store/embedding_store.py#L131)

## cdm/store/index_manager.py

[Source](../../../cdm/store/index_manager.py)

- function: [`_prefixed(name: str) -> str`](../../../cdm/store/index_manager.py#L37)
- function: [`_inject_lemma_siblings(properties: dict) -> None`](../../../cdm/store/index_manager.py#L42)
- function: [`load_definitions() -> dict[str, dict]`](../../../cdm/store/index_manager.py#L68)
- function: [`lemma_field_paths(name: str) -> tuple[tuple[str, ...], ...]`](../../../cdm/store/index_manager.py#L85)
- field: [`lemma_field_paths.paths: list[tuple[str, ...]]`](../../../cdm/store/index_manager.py#L90)
- function: [`lemma_field_paths.walk(properties: dict, prefix: tuple[str, ...]) -> None`](../../../cdm/store/index_manager.py#L92)
- class: [`IndexManager()`](../../../cdm/store/index_manager.py#L111)
- function: [`IndexManager.__init__(self, client: Elasticsearch, *, dry_run: bool=False) -> None`](../../../cdm/store/index_manager.py#L124)
- function: [`IndexManager.definitions(self) -> dict[str, dict]`](../../../cdm/store/index_manager.py#L132)
- function: [`IndexManager.index_names(self) -> list[str]`](../../../cdm/store/index_manager.py#L137)
- function: [`IndexManager._versioned_mapping(definition: dict) -> dict`](../../../cdm/store/index_manager.py#L142)
- function: [`IndexManager._normalize_mapping(value: Any) -> Any`](../../../cdm/store/index_manager.py#L150)
- function: [`IndexManager.create(self, name: str, *, exists_ok: bool=True) -> None`](../../../cdm/store/index_manager.py#L167)
- field: [`IndexManager.create.body: dict`](../../../cdm/store/index_manager.py#L191)
- function: [`IndexManager.create_versioned(self, name: str, version: int=2) -> str`](../../../cdm/store/index_manager.py#L201)
- function: [`IndexManager.reindex_to_versioned(self, name: str, version: int=2) -> dict`](../../../cdm/store/index_manager.py#L225)
- function: [`IndexManager.validate_versioned(self, name: str, version: int=2) -> dict`](../../../cdm/store/index_manager.py#L253)
- function: [`IndexManager.ensure_aliases(self, name: str) -> None`](../../../cdm/store/index_manager.py#L314)
- function: [`IndexManager.switch_aliases_to_versioned(self, name: str, version: int=2) -> dict`](../../../cdm/store/index_manager.py#L334)
- function: [`IndexManager.update(self, name: str) -> None`](../../../cdm/store/index_manager.py#L353)
- function: [`IndexManager.delete(self, name: str, *, confirm: bool=False) -> None`](../../../cdm/store/index_manager.py#L376)
- function: [`IndexManager.create_all(self, *, exists_ok: bool=True) -> None`](../../../cdm/store/index_manager.py#L392)
- function: [`IndexManager.update_all(self) -> None`](../../../cdm/store/index_manager.py#L397)
- function: [`IndexManager.status(self) -> list[dict]`](../../../cdm/store/index_manager.py#L404)
- function: [`IndexManager.audit(self) -> dict`](../../../cdm/store/index_manager.py#L429)

## cdm/store/indexer.py

[Source](../../../cdm/store/indexer.py)

- function: [`_bioguide_ids(value: object) -> list[str]`](../../../cdm/store/indexer.py#L25)
- function: [`_collect_lemma_targets(container: object, path: tuple[str, ...], targets: list[tuple[dict, str, str]]) -> None`](../../../cdm/store/indexer.py#L36)
- function: [`_apply_lemmas(doc: dict, target: str) -> None`](../../../cdm/store/indexer.py#L56)
- field: [`_apply_lemmas.targets: list[tuple[dict, str, str]]`](../../../cdm/store/indexer.py#L58)
- function: [`to_document(record: dict, resource: str, *, raw_record: dict \| None=None, preserve_raw: bool=False, ingest_metadata: Mapping[str, object] \| None=None) -> dict`](../../../cdm/store/indexer.py#L69)

## cdm/store/mapping_validation.py

[Source](../../../cdm/store/mapping_validation.py)

- function: [`_properties(resource: str) -> tuple[str, dict]`](../../../cdm/store/mapping_validation.py#L11)
- function: [`audit_document(document: dict, resource: str) -> dict`](../../../cdm/store/mapping_validation.py#L19)
- function: [`validate_document(document: dict, resource: str) -> dict`](../../../cdm/store/mapping_validation.py#L40)

## cdm/store/metasubject_override_store.py

[Source](../../../cdm/store/metasubject_override_store.py)

- class: [`OverrideField(StrEnum)`](../../../cdm/store/metasubject_override_store.py#L17)
- class: [`OverrideVersion(BaseModel)`](../../../cdm/store/metasubject_override_store.py#L24)
- field: [`OverrideVersion.metasubject_id: int`](../../../cdm/store/metasubject_override_store.py#L27)
- field: [`OverrideVersion.version: int`](../../../cdm/store/metasubject_override_store.py#L28)
- field: [`OverrideVersion.name: str \| None`](../../../cdm/store/metasubject_override_store.py#L29)
- field: [`OverrideVersion.created_at: datetime`](../../../cdm/store/metasubject_override_store.py#L30)
- class: [`MetasubjectOverrideStore()`](../../../cdm/store/metasubject_override_store.py#L33)
- function: [`MetasubjectOverrideStore.__init__(self, client: Elasticsearch, index: str) -> None`](../../../cdm/store/metasubject_override_store.py#L34)
- function: [`MetasubjectOverrideStore.ensure_index(self) -> None`](../../../cdm/store/metasubject_override_store.py#L38)
- function: [`MetasubjectOverrideStore.history(self, metasubject_id: int \| None=None) -> list[OverrideVersion]`](../../../cdm/store/metasubject_override_store.py#L53)
- field: [`MetasubjectOverrideStore.history.query: JsonObject`](../../../cdm/store/metasubject_override_store.py#L57)
- function: [`MetasubjectOverrideStore.current(self) -> MetasubjectOverrides`](../../../cdm/store/metasubject_override_store.py#L71)
- field: [`MetasubjectOverrideStore.current.latest: dict[int, OverrideVersion]`](../../../cdm/store/metasubject_override_store.py#L73)
- function: [`MetasubjectOverrideStore._append(self, metasubject_id: int, name: str \| None) -> OverrideVersion`](../../../cdm/store/metasubject_override_store.py#L80)
- function: [`MetasubjectOverrideStore.set_name(self, metasubject_id: int, name: str) -> OverrideVersion`](../../../cdm/store/metasubject_override_store.py#L97)
- function: [`MetasubjectOverrideStore.clear(self, metasubject_id: int) -> OverrideVersion`](../../../cdm/store/metasubject_override_store.py#L100)

## cdm/store/metasubject_repository.py

[Source](../../../cdm/store/metasubject_repository.py)

- class: [`MetasubjectRepository()`](../../../cdm/store/metasubject_repository.py#L13)
- function: [`MetasubjectRepository.__init__(self, client: Elasticsearch, index: str, publications: TopicPublicationStore \| None=None) -> None`](../../../cdm/store/metasubject_repository.py#L14)
- function: [`MetasubjectRepository.latest(self) -> list[Metasubject]`](../../../cdm/store/metasubject_repository.py#L24)

## cdm/store/opensearch.py

[Source](../../../cdm/store/opensearch.py)

- field: [`_RESOURCE_TARGETS: dict[str, tuple[str, dict[str, str]]]`](../../../cdm/store/opensearch.py#L19)
- function: [`resource_target(resource: str) -> tuple[str, dict[str, str]]`](../../../cdm/store/opensearch.py#L38)
- function: [`index_name(resource: str) -> str`](../../../cdm/store/opensearch.py#L47)
- function: [`write_alias(resource: str) -> str`](../../../cdm/store/opensearch.py#L53)
- function: [`read_alias(resource: str) -> str`](../../../cdm/store/opensearch.py#L57)
- function: [`bill_text_parent_action(doc: dict, index: str) -> JsonObject \| None`](../../../cdm/store/opensearch.py#L96)
- function: [`bulk_upsert(client: Elasticsearch, resource: str, docs: Iterable[dict], *, target_index: str \| None=None, replace: bool=False) -> dict[str, int \| bool]`](../../../cdm/store/opensearch.py#L135)

## cdm/store/perspective_repository.py

[Source](../../../cdm/store/perspective_repository.py)

- class: [`PerspectivePublication(BaseModel)`](../../../cdm/store/perspective_repository.py#L22)
- field: [`PerspectivePublication.kind: Literal[PerspectiveKind.PUBLICATION]`](../../../cdm/store/perspective_repository.py#L25)
- field: [`PerspectivePublication.congress: int`](../../../cdm/store/perspective_repository.py#L26)
- field: [`PerspectivePublication.model_version: str`](../../../cdm/store/perspective_repository.py#L27)
- field: [`PerspectivePublication.built_at: AwareDatetime`](../../../cdm/store/perspective_repository.py#L28)
- field: [`PerspectivePublication.results: list[TopicPerspectives]`](../../../cdm/store/perspective_repository.py#L29)
- function: [`PerspectivePublication.document_id(congress: int) -> str`](../../../cdm/store/perspective_repository.py#L32)
- function: [`PerspectivePublication.validate_scope(self) -> Self`](../../../cdm/store/perspective_repository.py#L36)
- class: [`PerspectiveRepository()`](../../../cdm/store/perspective_repository.py#L44)
- function: [`PerspectiveRepository.__init__(self, client: Elasticsearch, index: str, settings: PerspectiveStoreConfig \| None=None) -> None`](../../../cdm/store/perspective_repository.py#L45)
- function: [`PerspectiveRepository.congresses(self) -> list[int]`](../../../cdm/store/perspective_repository.py#L55)
- function: [`PerspectiveRepository.read(self, congress: int) -> tuple[list[TopicPerspectives], str \| None]`](../../../cdm/store/perspective_repository.py#L78)
- function: [`PerspectiveRepository._legacy_read(self, congress: int) -> tuple[list[TopicPerspectives], str \| None]`](../../../cdm/store/perspective_repository.py#L91)
- function: [`PerspectiveRepository.replace(self, congress: int, model_version: str, built_at: datetime, results: Sequence[TopicPerspectives]) -> int`](../../../cdm/store/perspective_repository.py#L121)

## cdm/store/topic_publication.py

[Source](../../../cdm/store/topic_publication.py)

- class: [`TopicRunCounts(BaseModel)`](../../../cdm/store/topic_publication.py#L20)
- field: [`TopicRunCounts.topics: int`](../../../cdm/store/topic_publication.py#L23)
- field: [`TopicRunCounts.assignments: int`](../../../cdm/store/topic_publication.py#L24)
- field: [`TopicRunCounts.over_time: int`](../../../cdm/store/topic_publication.py#L25)
- field: [`TopicRunCounts.metasubjects: int`](../../../cdm/store/topic_publication.py#L26)
- field: [`TopicRunCounts.metasubject_over_time: int`](../../../cdm/store/topic_publication.py#L27)
- function: [`TopicRunCounts.by_kind(self) -> dict[TopicKind, int]`](../../../cdm/store/topic_publication.py#L29)
- function: [`TopicRunCounts.total(self) -> int`](../../../cdm/store/topic_publication.py#L39)
- class: [`TopicRunSpecification(BaseModel)`](../../../cdm/store/topic_publication.py#L43)
- field: [`TopicRunSpecification.model_version: str`](../../../cdm/store/topic_publication.py#L46)
- field: [`TopicRunSpecification.trained_at: AwareDatetime`](../../../cdm/store/topic_publication.py#L47)
- field: [`TopicRunSpecification.embedding_model: str`](../../../cdm/store/topic_publication.py#L48)
- field: [`TopicRunSpecification.embedding_cache: EmbeddingCache \| None`](../../../cdm/store/topic_publication.py#L49)
- field: [`TopicRunSpecification.min_congress: int`](../../../cdm/store/topic_publication.py#L50)
- field: [`TopicRunSpecification.corpus_size: int`](../../../cdm/store/topic_publication.py#L51)
- field: [`TopicRunSpecification.dated_documents: int`](../../../cdm/store/topic_publication.py#L52)
- field: [`TopicRunSpecification.model_path: str`](../../../cdm/store/topic_publication.py#L53)
- field: [`TopicRunSpecification.counts: TopicRunCounts`](../../../cdm/store/topic_publication.py#L54)
- function: [`TopicRunSpecification.validate_corpus_counts(self) -> Self`](../../../cdm/store/topic_publication.py#L57)
- class: [`CompletedTopicRun(TopicRunSpecification)`](../../../cdm/store/topic_publication.py#L71)
- field: [`CompletedTopicRun.kind: Literal[TopicKind.RUN]`](../../../cdm/store/topic_publication.py#L72)
- field: [`CompletedTopicRun.completed_at: AwareDatetime`](../../../cdm/store/topic_publication.py#L73)
- function: [`CompletedTopicRun.id(self) -> str`](../../../cdm/store/topic_publication.py#L76)
- class: [`TopicPublicationPointer(BaseModel)`](../../../cdm/store/topic_publication.py#L80)
- field: [`TopicPublicationPointer.kind: Literal[TopicKind.POINTER]`](../../../cdm/store/topic_publication.py#L83)
- field: [`TopicPublicationPointer.run: CompletedTopicRun`](../../../cdm/store/topic_publication.py#L84)
- class: [`TopicPublicationSnapshot(BaseModel)`](../../../cdm/store/topic_publication.py#L87)
- field: [`TopicPublicationSnapshot.pointer: TopicPublicationPointer`](../../../cdm/store/topic_publication.py#L90)
- field: [`TopicPublicationSnapshot.seq_no: int`](../../../cdm/store/topic_publication.py#L91)
- field: [`TopicPublicationSnapshot.primary_term: int`](../../../cdm/store/topic_publication.py#L92)
- class: [`_KindCount(BaseModel)`](../../../cdm/store/topic_publication.py#L95)
- field: [`_KindCount.key: TopicKind`](../../../cdm/store/topic_publication.py#L96)
- field: [`_KindCount.doc_count: int`](../../../cdm/store/topic_publication.py#L97)
- class: [`TopicPublicationStore()`](../../../cdm/store/topic_publication.py#L100)
- function: [`TopicPublicationStore.__init__(self, client: Elasticsearch, index: str) -> None`](../../../cdm/store/topic_publication.py#L101)
- function: [`TopicPublicationStore.ensure_index(self) -> None`](../../../cdm/store/topic_publication.py#L105)
- function: [`TopicPublicationStore.snapshot(self) -> TopicPublicationSnapshot \| None`](../../../cdm/store/topic_publication.py#L114)
- function: [`TopicPublicationStore.current(self) -> CompletedTopicRun \| None`](../../../cdm/store/topic_publication.py#L125)
- function: [`TopicPublicationStore._verify_counts(self, specification: TopicRunSpecification) -> None`](../../../cdm/store/topic_publication.py#L129)
- function: [`TopicPublicationStore._verify_cache(self, specification: TopicRunSpecification) -> None`](../../../cdm/store/topic_publication.py#L155)
- function: [`TopicPublicationStore.write(self, specification: TopicRunSpecification, actions: Iterable[JsonObject]) -> CompletedTopicRun`](../../../cdm/store/topic_publication.py#L166)
- function: [`TopicPublicationStore.publish(self, model_version: str, expected: TopicPublicationSnapshot \| None) -> CompletedTopicRun`](../../../cdm/store/topic_publication.py#L199)

"""Validated, immutable topic runs and an atomic published-version pointer."""

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Literal, Self

from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch.helpers import bulk
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from cdm.config.topic_analysis import (
    EmbeddingCache,
    TopicAnalysisSchema,
    TopicKind,
    TopicPublicationId,
)
from cdm.utils.json_types import JsonObject


class TopicRunCounts(BaseModel):
    model_config = ConfigDict(frozen=True)

    topics: int = Field(ge=1)
    assignments: int = Field(ge=1)
    over_time: int = Field(ge=0)
    metasubjects: int = Field(ge=1)
    metasubject_over_time: int = Field(ge=0)

    def by_kind(self) -> dict[TopicKind, int]:
        return {
            TopicKind.TOPIC: self.topics,
            TopicKind.ASSIGNMENT: self.assignments,
            TopicKind.OVER_TIME: self.over_time,
            TopicKind.METASUBJECT: self.metasubjects,
            TopicKind.METASUBJECT_OVER_TIME: self.metasubject_over_time,
        }

    @property
    def total(self) -> int:
        return sum(self.by_kind().values())


class TopicRunSpecification(BaseModel):
    model_config = ConfigDict(frozen=True)

    model_version: str = Field(min_length=1)
    trained_at: AwareDatetime
    embedding_model: str = Field(min_length=1)
    embedding_cache: EmbeddingCache | None = None
    min_congress: int = Field(gt=0)
    corpus_size: int = Field(gt=0)
    dated_documents: int = Field(ge=0)
    model_path: str = Field(min_length=1)
    counts: TopicRunCounts

    @model_validator(mode="after")
    def validate_corpus_counts(self) -> Self:
        if self.embedding_cache and self.embedding_cache.model != self.embedding_model:
            raise ValueError(
                "Embedding cache identity must match the run's embedding model"
            )
        if self.corpus_size != self.counts.assignments:
            raise ValueError("Assignment count must match the complete fetched corpus")
        if self.dated_documents > self.corpus_size:
            raise ValueError(
                "Dated documents cannot exceed the complete fetched corpus"
            )
        return self


class CompletedTopicRun(TopicRunSpecification):
    kind: Literal[TopicKind.RUN] = TopicKind.RUN
    completed_at: AwareDatetime

    @property
    def id(self) -> str:
        return f"{TopicKind.RUN}:{self.model_version}"


class TopicPublicationPointer(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal[TopicKind.POINTER] = TopicKind.POINTER
    run: CompletedTopicRun


class TopicPublicationSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    pointer: TopicPublicationPointer
    seq_no: int
    primary_term: int


class _KindCount(BaseModel):
    key: TopicKind
    doc_count: int


class TopicPublicationStore:
    def __init__(self, client: Elasticsearch, index: str) -> None:
        self.client = client
        self.index = index

    def ensure_index(self) -> None:
        properties = TopicAnalysisSchema.properties()
        if not self.client.indices.exists(index=self.index):
            result = self.client.indices.create(
                index=self.index, mappings={"properties": properties}
            )
        else:
            mapping = self.client.indices.get_mapping(index=self.index)[self.index][
                "mappings"
            ]
            additions = TopicAnalysisSchema.missing_properties(mapping)
            if not additions:
                return
            result = self.client.indices.put_mapping(
                index=self.index, properties=additions
            )
        if not result["acknowledged"]:
            raise RuntimeError("Topic-analysis mapping change was not acknowledged")

    def snapshot(self) -> TopicPublicationSnapshot | None:
        try:
            response = self.client.get(index=self.index, id=TopicPublicationId.CURRENT)
        except NotFoundError:
            return None
        return TopicPublicationSnapshot(
            pointer=TopicPublicationPointer.model_validate(response["_source"]),
            seq_no=response["_seq_no"],
            primary_term=response["_primary_term"],
        )

    def current(self) -> CompletedTopicRun | None:
        snapshot = self.snapshot()
        return snapshot.pointer.run if snapshot else None

    def _verify_counts(self, specification: TopicRunSpecification) -> None:
        expected = specification.counts.by_kind()
        self.client.indices.refresh(index=self.index)
        response = self.client.search(
            index=self.index,
            size=0,
            allow_partial_search_results=False,
            query={
                "bool": {
                    "filter": [
                        {"term": {"model_version": specification.model_version}},
                        {"terms": {"kind": list(expected)}},
                    ]
                }
            },
            aggs={"counts": {"terms": {"field": "kind", "size": len(expected)}}},
        )
        observed = dict.fromkeys(expected, 0)
        for value in response["aggregations"]["counts"]["buckets"]:
            bucket = _KindCount.model_validate(value)
            observed[bucket.key] = bucket.doc_count
        if observed != expected:
            raise ValueError(
                f"Incomplete topic run: expected {expected}, observed {observed}"
            )

    def _verify_cache(self, specification: TopicRunSpecification) -> None:
        if cache := specification.embedding_cache:
            cache.verify_mapping(
                self.client.indices.get_mapping(index=cache.index)[cache.index][
                    "mappings"
                ]
            )
            refreshed = self.client.indices.refresh(index=cache.index)
            if refreshed["_shards"]["failed"]:
                raise RuntimeError("Embedding cache refresh failed")

    def write(
        self, specification: TopicRunSpecification, actions: Iterable[JsonObject]
    ) -> CompletedTopicRun:
        self.ensure_index()
        self._verify_cache(specification)
        written, errors = bulk(
            self.client,
            ({**action, "_op_type": "create"} for action in actions),
            raise_on_error=False,
        )
        if not isinstance(errors, list):
            raise TypeError("Expected per-item bulk results for topic publication")
        if errors or written != specification.counts.total:
            raise RuntimeError(
                f"Incomplete topic bulk: {written}/{specification.counts.total} "
                f"written, errors={errors[:5]}"
            )
        self._verify_counts(specification)
        completed = CompletedTopicRun.model_validate(
            {
                **specification.model_dump(),
                "completed_at": datetime.now(UTC),
            }
        )
        self.client.index(
            index=self.index,
            id=completed.id,
            document=completed.model_dump(mode="json"),
            op_type="create",
            refresh="wait_for",
        )
        return completed

    def publish(
        self, model_version: str, expected: TopicPublicationSnapshot | None
    ) -> CompletedTopicRun:
        try:
            response = self.client.get(
                index=self.index, id=f"{TopicKind.RUN}:{model_version}"
            )
        except NotFoundError as exc:
            raise ValueError(
                f"No validated complete topic run: {model_version}"
            ) from exc
        run = CompletedTopicRun.model_validate(response["_source"])
        if run.model_version != model_version:
            raise ValueError(
                "Topic manifest identity does not match the requested version"
            )
        if (
            expected
            and expected.pointer.run.embedding_model != run.embedding_model
            and run.embedding_cache is None
        ):
            raise ValueError(
                "Changing embedding models requires a separate cache migration"
            )
        self._verify_counts(run)
        self._verify_cache(run)
        pointer = TopicPublicationPointer(run=run)
        if expected is None:
            self.client.index(
                index=self.index,
                id=TopicPublicationId.CURRENT,
                document=pointer.model_dump(mode="json"),
                op_type="create",
                refresh="wait_for",
            )
        else:
            self.client.index(
                index=self.index,
                id=TopicPublicationId.CURRENT,
                document=pointer.model_dump(mode="json"),
                if_seq_no=expected.seq_no,
                if_primary_term=expected.primary_term,
                refresh="wait_for",
            )
        return run

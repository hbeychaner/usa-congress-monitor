"""Topic-analysis schema and typed training options."""

from datetime import timedelta
from enum import IntEnum, StrEnum
from pathlib import Path
from typing import Self

from pydantic import AliasPath, BaseModel, ConfigDict, Field, model_validator

from cdm.utils.json_types import JsonObject


class TopicKind(StrEnum):
    TOPIC = "topic"
    ASSIGNMENT = "assignment"
    OVER_TIME = "topic_over_time"
    METASUBJECT = "metasubject"
    METASUBJECT_OVER_TIME = "metasubject_over_time"
    RUN = "topic_model_run"
    POINTER = "topic_model_pointer"


class TopicId(IntEnum):
    OUTLIER = -1


class TopicPublicationId(StrEnum):
    CURRENT = "topic-model:published"


class PerspectiveKind(StrEnum):
    PARTY_TOPIC = "party_topic"
    PUBLICATION = "party_topic_publication"


class PerspectiveField(StrEnum):
    MODEL_VERSION = "model_version"
    BUILT_AT = "built_at"
    CONGRESS = "congress"


class PerspectiveStoreConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    legacy_limit: int = Field(default=10000, gt=0)
    congress_buckets: int = Field(default=200, gt=0)


class PerspectiveSchema:
    @staticmethod
    def properties() -> dict[str, JsonObject]:
        return {
            "kind": {"type": "keyword"},
            PerspectiveField.MODEL_VERSION: {"type": "keyword"},
            PerspectiveField.CONGRESS: {"type": "integer"},
            PerspectiveField.BUILT_AT: {"type": "date"},
            "results": {"type": "object", "enabled": False},
        }


class TopicTrainingOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_docs: int | None = Field(default=None, gt=0)
    min_congress: int = Field(default=113, gt=0)
    min_topic_size: int = Field(default=25, ge=2)
    nr_bins: int = Field(default=60, gt=0)
    embedding_model: str | None = Field(default=None, min_length=1)
    model_dir: Path = Path("models/topics")
    no_llm_labels: bool = False
    dry_run: bool = False
    publish_version: str | None = Field(default=None, min_length=1)

    @property
    def preview(self) -> bool:
        return self.dry_run or self.max_docs is not None

    @model_validator(mode="after")
    def validate_publication_mode(self) -> Self:
        if self.publish_version and self.preview:
            raise ValueError(
                "Publishing an existing run cannot be combined with a preview"
            )
        return self


class TopicReadConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    terms_chunk: int = 1024
    metasubject_limit: int = 100
    metasubject_trend_limit: int = 10000
    related_metasubject_limit: int = 5
    related_topic_limit: int = 10
    topic_limit: int = 10000


class GraphHealthConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    max_age: timedelta = timedelta(days=9)


class GraphStoreConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    index: str = "analysis_graph"
    first_congress: int = Field(default=113, gt=0)
    write_batch: int = Field(default=5000, gt=0)


class VoteRepairField(StrEnum):
    YEA_IDS = "yea_ids"
    NAY_IDS = "nay_ids"
    PRESENT_IDS = "present_ids"
    NOT_VOTING_IDS = "not_voting_ids"
    PARTY_POSITIONS = "party_positions"
    PARTY_SPLIT = "party_split"
    DEFECTOR_IDS = "defector_ids"
    YEA_COUNT = "yea_count"
    NAY_COUNT = "nay_count"


class GraphRepairConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    congress: int = Field(default=114, ge=114, le=114)
    first_congress: int = Field(default=113, gt=0, le=114)
    expected_house: int = Field(default=1322, ge=0)
    expected_senate: int = Field(default=502, ge=0)
    max_source_records: int = Field(default=20000, gt=0)
    max_graph_records: int = Field(default=2000000, gt=0)
    cache_dir: Path = Path("data/voteview")


class GraphRepairMappingField(StrEnum):
    SOURCE_MODEL_VERSION = "source_model_version"
    CONGRESSES = "congresses"
    SHARED_VOTES = "shared_votes"
    SHARED_TOPICS = "shared_topics"
    CONGRESS_SHARED_VOTES = "by_congress.shared_votes"
    CONGRESS_AGREED_VOTES = "by_congress.agreed_votes"
    CONGRESS_SHARED_SPLIT_VOTES = "by_congress.shared_split_votes"
    CONGRESS_AGREED_SPLIT_VOTES = "by_congress.agreed_split_votes"


class EmbeddingSearchConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_factor: int = Field(default=10, gt=0)


class EmbeddingCache(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    index: str = Field(min_length=1)
    model: str = Field(
        min_length=1, validation_alias=AliasPath("_meta", "embedding_model")
    )
    dimensions: int = Field(
        gt=0, validation_alias=AliasPath("properties", "embedding", "dims")
    )

    def mappings(self) -> dict[str, JsonObject]:
        return {
            "_meta": {"embedding_model": self.model},
            "properties": {
                "model": {"type": "keyword"},
                "content_hash": {"type": "keyword", "index": False},
                "embedded_at": {"type": "date"},
                "embedding": {
                    "type": "dense_vector",
                    "dims": self.dimensions,
                    "index": True,
                    "similarity": "cosine",
                },
            },
        }

    def verify_mapping(self, mapping: JsonObject) -> None:
        observed = EmbeddingCache.model_validate({"index": self.index, **mapping})
        if observed != self:
            raise ValueError(
                f"Incompatible embedding cache: expected {self}, observed {observed}"
            )


class TrainingProgressConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    fetch: float = 0.0
    embed: float = 0.05
    cluster: float = 0.55
    trends: float = 0.80
    labels: float = 0.85
    groups: float = 0.92
    index: float = 0.95
    done: float = 1.0


class LabelPreviewConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    sample_docs: int = 8
    min_size: int = 15
    topic_limit: int = 10000


class TopicAnalysisSchema:
    @staticmethod
    def properties() -> dict[str, JsonObject]:
        return {
            "kind": {"type": "keyword"},
            "model_version": {"type": "keyword"},
            "trained_at": {"type": "date"},
            "topic_id": {"type": "integer"},
            "name": {"type": "keyword"},
            "label": {"type": "keyword"},
            "label_source": {"type": "keyword"},
            "fallback_reason": {"type": "keyword"},
            "size": {"type": "integer"},
            "top_words": {"type": "keyword"},
            "doc_id": {"type": "keyword"},
            "probability": {"type": "float"},
            "words": {"type": "text"},
            "frequency": {"type": "integer"},
            "timestamp": {"type": "date"},
            "metasubject_id": {"type": "integer"},
            "metasubject_confidence": {"type": "float"},
            "assigned_by": {"type": "keyword"},
            "low_confidence": {"type": "boolean"},
            "topic_ids": {"type": "integer"},
            "centroid": {"type": "float", "index": False, "doc_values": False},
            "run": {"type": "object", "enabled": False},
        }

"""Typed application configuration, grouped by concern and loaded from the environment."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILES = (REPO_ROOT / ".env", REPO_ROOT / "elastic-start-local" / ".env")


class _Section(BaseSettings):
    """Base for one config section; field names are the lower-cased env var names."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILES, env_file_encoding="utf-8", extra="ignore"
    )


class ElasticConfig(_Section):
    es_local_url: str = ""
    es_local_api_key: str = ""
    elastic_api_url: str = ""
    elastic_api_key: str = ""
    # Bill index in which the 118th-congress staging copy lives.
    staging_index: str = "congress-legislation-v118"
    analysis_index: str = "congress-analysis-topics"
    embeddings_index: str = "congress-embeddings"
    metasubject_overrides_index: str = "congress-metasubject-overrides"


class CongressApiConfig(_Section):
    congress_api_key: str = ""
    congress_api_url: str = ""
    congress_strict_field_check: bool = True
    timeout_secs: int = 30


class OpenAIConfig(_Section):
    openai_api_key: str = ""


class OllamaConfig(_Section):
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    ollama_timeout_secs: float = 60.0
    ollama_probe_timeout_secs: float = 3.0
    ollama_temperature: float = 0.2


class QueueConfig(_Section):
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    rabbitmq_queue: str = "congress-sync"
    rabbitmq_prefetch: int = 10
    rabbitmq_rate_limit_per_hour: int = 5000
    rabbitmq_page_size: int = 250
    rabbitmq_api_workers: int = 4
    celery_task_queue: str = "congress-sync"
    celery_ingest_queue: str = "congress-ingest"
    # Bulk fan-out gets its own queue so it cannot starve operational traffic.
    celery_bulk_queue: str = "congress-bulk"
    celery_index_queue: str = "congress-index"
    celery_retry_max: int = 8
    celery_retry_max_transient: int = 24
    celery_retry_backoff_max: int = 3600
    celery_task_soft_time_limit: int = 3600
    celery_task_time_limit: int = 3900


class RedisConfig(_Section):
    redis_url: str = "redis://localhost:6379/0"
    redis_stream_maxlen: int = 1_000_000
    redis_consumer_group: str = "congress-indexers"


class LedgerConfig(_Section):
    job_db_path: str = "data/jobs.sqlite3"
    # Terminal jobs older than this are pruned with their streams and archives.
    retention_days: int = 30
    # Ledger windows older than this are not scanned for interior coverage holes.
    coverage_lookback_days: int = 30


class GovInfoConfig(_Section):
    # Per-worker-process download pacing; unpaced parallel downloads get throttled.
    govinfo_rate_limit_per_hour: int = 1200
    govinfo_archive_root: Path = Path("data/full_history/govinfo")
    govinfo_billstatus_dir: str = "BILLSTATUS"
    govinfo_billstatus_suffix: str = ".xml"
    committee_backfill_batch_size: int = 500
    committee_backfill_request_timeout: int = 120


class IndexingConfig(_Section):
    index_batch_jobs: int = 25
    index_batch_docs: int = 1000


class EmbeddingConfig(_Section):
    embedding_model: str = "all-mpnet-base-v2"
    embedding_batch_docs: int = 500


class MetasubjectConfig(_Section):
    # Topics are clustered into this many broad metasubjects.
    metasubject_target_groups: int = 30
    # A retrained group keeps its id when its centroid is at least this similar.
    metasubject_match_min_similarity: float = 0.85
    # Bills below this similarity to their centroid are flagged low confidence.
    metasubject_low_confidence_similarity: float = 0.35


class ApiConfig(_Section):
    cors_origins_csv: str = Field(
        default="http://localhost:5183,http://localhost:5173",
        validation_alias="CORS_ORIGINS",
    )
    log_level: str = "INFO"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins_csv.split(",") if o.strip()]


class AppConfig(BaseModel):
    """Every configuration section; build one per process and inject its parts."""

    elastic: ElasticConfig = Field(default_factory=ElasticConfig)
    congress_api: CongressApiConfig = Field(default_factory=CongressApiConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    queue: QueueConfig = Field(default_factory=QueueConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    ledger: LedgerConfig = Field(default_factory=LedgerConfig)
    govinfo: GovInfoConfig = Field(default_factory=GovInfoConfig)
    indexing: IndexingConfig = Field(default_factory=IndexingConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    metasubject: MetasubjectConfig = Field(default_factory=MetasubjectConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)


@lru_cache
def get_config() -> AppConfig:
    return AppConfig()

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
    # Shared per-ingest-job request budget.
    ingest_rate_limit_per_hour: int = 4800
    # Redis key holding the budget shared by every worker process.
    ingest_rate_limit_key: str = "congress:api:rate"


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
    # Light periodic upkeep gets its own queue so busy ingest workers cannot starve it.
    celery_maintenance_queue: str = "congress-maintenance"
    celery_retry_max: int = 8
    # Few ingest jobs at a time so each finishes instead of all crawling together.
    ingest_max_concurrent_jobs: int = 2
    ingest_defer_seconds: int = 300
    celery_retry_max_transient: int = 24
    celery_retry_backoff_max: int = 3600
    # Running jobs touch their ledger row this often; recovery treats silence as a crash.
    job_heartbeat_seconds: float = 60.0
    celery_task_soft_time_limit: int = 3600
    celery_task_time_limit: int = 3900
    # Ingest jobs may run for days; they are bounded by stalls, not elapsed time.
    celery_ingest_soft_time_limit: int = 5 * 24 * 3600
    celery_ingest_time_limit: int = 5 * 24 * 3600 + 3600


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
    # Latest copy of each refreshed record, kept outside job directories.
    record_library_root: Path = Path("data/record_library")


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
    # Running ingest jobs queue an index job after this many new records.
    ingest_partial_index_every: int = 100


class EmbeddingConfig(_Section):
    embedding_model: str = "all-mpnet-base-v2"
    embedding_batch_docs: int = 500


class MetasubjectConfig(_Section):
    # Topics are clustered into this many broad metasubjects.
    metasubject_target_groups: int = 30
    # A retrained group keeps its id when its centroid is at least this similar.
    metasubject_match_min_similarity: float = 0.85
    # Bills below this similarity to their centroid are flagged low confidence.
    metasubject_low_confidence_similarity: float = 0.5
    # A matched group keeps its old name only if its size changed by less than this factor.
    metasubject_name_carry_max_size_ratio: float = 3.0


class PerspectiveConfig(_Section):
    # Each (Congress, topic) is clustered separately; smaller topics are left whole.
    perspective_min_bills: int = 40
    # Topics below this size are not analysed for the parties page.
    perspective_min_topic_bills: int = 20
    # Topics listed per party on the parties page.
    perspective_ranking_size: int = 25
    perspective_min_cluster_bills: int = 8
    perspective_max_clusters: int = 6
    # A split passes only if its silhouette and its stability across seeds reach these values.
    perspective_min_silhouette: float = 0.05
    perspective_min_stability: float = 0.6
    perspective_stability_runs: int = 5
    perspective_svd_dims: int = 20
    # Only the start of each bill's text is used, which carries its purpose and operative terms.
    perspective_text_chars: int = 30000
    perspective_random_seed: int = 7
    perspective_top_terms: int = 20
    # Longest phrase length in words; 2 is bigrams only.
    perspective_max_ngram: int = 3
    perspective_term_min_docs: int = 3
    perspective_sample_bills: int = 6
    # Each party needs this many bills in a topic before their terms are contrasted.
    perspective_party_min_bills: int = 10
    # A bill is bipartisan with this many cosponsors from the party opposite its sponsor's.
    perspective_bipartisan_min_cosponsors: int = 2
    # A topic shows Bilateral Support when this share of its bills are bipartisan.
    perspective_bilateral_min_share: float = 0.25
    # A term prominent in this share of a topic's bills counts as present in that topic.
    perspective_boilerplate_topic_share: float = 0.15
    # A term present in this share of topics is boilerplate, not subject matter.
    perspective_boilerplate_topic_spread: float = 0.2
    # A term used in at least min_docs bills of this share of topics is boilerplate too.
    perspective_boilerplate_presence_spread: float = 0.4
    # A word in this share of all policy bills is boilerplate whatever its topics.
    perspective_boilerplate_corpus_share: float = 0.12
    perspective_boilerplate_min_docs: int = 5
    perspective_boilerplate_min_topic_bills: int = 20
    # Simple and concurrent resolutions and ceremonial measures carry no policy approach.
    perspective_excluded_types: list[str] = ["hres", "sres", "hconres", "sconres"]
    perspective_excluded_title_pattern: str = (
        r"post office|postal service|designate the (facility|building)|"
        r"(rename|redesignate|name) the|for the relief of|gold medal|"
        r"commemorat|congressional recognition|"
        r"^providing for (the )?(consideration|expeditious)|^waiving (all )?points"
    )


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
    perspective: PerspectiveConfig = Field(default_factory=PerspectiveConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)


@lru_cache
def get_config() -> AppConfig:
    return AppConfig()

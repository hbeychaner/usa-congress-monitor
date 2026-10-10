from __future__ import annotations

from cdm.config import AppConfig, ElasticConfig, MetasubjectConfig
from cdm.container import Container


def _config() -> AppConfig:
    return AppConfig(
        elastic=ElasticConfig(
            es_local_url="http://es:9200",
            es_local_api_key="key",
            embeddings_index="emb",
            metasubject_overrides_index="ovr",
        ),
        metasubject=MetasubjectConfig(
            metasubject_target_groups=7,
            metasubject_match_min_similarity=0.9,
            metasubject_low_confidence_similarity=0.2,
        ),
    )


def test_env_values_populate_sections(monkeypatch) -> None:
    monkeypatch.setenv("CELERY_RETRY_MAX", "3")
    monkeypatch.setenv("CORS_ORIGINS", "http://a, http://b")

    config = AppConfig()

    assert config.queue.celery_retry_max == 3
    assert config.api.cors_origins == ["http://a", "http://b"]


def test_container_injects_config_into_collaborators() -> None:
    container = Container(_config())
    container.__dict__["elastic_client"] = object()

    store = container.embedding_store("m")
    builder = container.metasubject_builder(container.metasubject_namer(use_llm=False))

    assert (store.index, store.model) == ("emb", "m")
    assert container.metasubject_override_store.index == "ovr"
    assert builder.target_groups == 7
    assert builder.matcher.min_similarity == 0.9


def test_container_replaces_providers_for_tests() -> None:
    container = Container(_config())
    fake = object()
    container.__dict__["elastic_client"] = fake

    assert container.committee_service.client is fake

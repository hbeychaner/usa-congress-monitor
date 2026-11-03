from __future__ import annotations

from unittest.mock import Mock

import pytest

from cdm.config import AppConfig, ElasticConfig, MetasubjectConfig
from cdm.config.topic_analysis import TopicTrainingOptions
from cdm.container import Container
from cdm.store.embedding_store import EmbeddingStore
from cdm.utils.metasubjects import Metasubject
from cdm.workers.runtime import WorkerContainer


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


def test_env_values_populate_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CELERY_RETRY_MAX", "3")
    monkeypatch.setenv("CORS_ORIGINS", "http://a, http://b")

    config = AppConfig()

    assert config.queue.celery_retry_max == 3
    assert config.api.cors_origins == ["http://a", "http://b"]


def test_container_injects_config_into_collaborators() -> None:
    container = WorkerContainer(_config())
    container.__dict__["elastic_client"] = object()

    store = container.embedding_store("m")
    job = container.topic_training_job(
        TopicTrainingOptions(publish_version="published-fixture"), Mock()
    )
    builder = job._builder

    assert (store.index, store.model) == (EmbeddingStore.namespace("emb", "m"), "m")
    assert container.similar_bill_service.store.index == "emb"
    assert container.metasubject_override_store.index == "ovr"
    assert builder.target_groups == 7
    assert builder.matcher.min_similarity == 0.9
    group = Metasubject(
        metasubject_id=1,
        name="Health",
        topic_ids=[1],
        size=1,
        top_words=["health"],
        centroid=[1.0],
    )
    assert job._assigner_factory([group]).low_confidence_below == 0.2


def test_container_replaces_providers_for_tests() -> None:
    container = Container(_config())
    fake = object()
    container.__dict__["elastic_client"] = fake

    assert container.committee_service.client is fake

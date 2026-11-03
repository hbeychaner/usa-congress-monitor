from datetime import UTC, datetime
from unittest.mock import Mock

import numpy as np
import pytest
from elastic_transport import ObjectApiResponse
from elasticsearch import Elasticsearch
from pydantic import ValidationError

from cdm.backend.services.similar_bill_service import SimilarBillService
from cdm.config.topic_analysis import EmbeddingCache
from cdm.store.embedding_store import EmbeddingNeighbors, EmbeddingStore
from cdm.store.topic_publication import (
    CompletedTopicRun,
    TopicPublicationStore,
    TopicRunCounts,
)
from cdm.utils.cached_embedder import CachedEmbedder, EmbeddingJob


def run(cache: EmbeddingCache | None) -> CompletedTopicRun:
    return CompletedTopicRun(
        model_version="run",
        trained_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        embedding_model=cache.model if cache else "legacy-model",
        embedding_cache=cache,
        min_congress=113,
        corpus_size=1,
        dated_documents=0,
        model_path="models/run",
        counts=TopicRunCounts(
            topics=1,
            assignments=1,
            over_time=0,
            metasubjects=1,
            metasubject_over_time=0,
        ),
    )


def test_model_namespaces_are_stable_distinct_and_index_safe() -> None:
    first = EmbeddingStore.namespace("emb", "Provider/Model A")
    assert first == EmbeddingStore.namespace("emb", "Provider/Model A")
    assert first != EmbeddingStore.namespace("emb", "Provider/Model B")
    assert first != EmbeddingStore.namespace("other", "Provider/Model A")
    assert len(first) == len("emb-") + 64
    assert all(
        character in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in first
    )


def test_similarity_tracks_hot_publication_changes_instead_of_configuration() -> None:
    store = Mock(spec=EmbeddingStore)
    store.similar.return_value = EmbeddingNeighbors(source_found=True, neighbors=[])
    publications = Mock(spec=TopicPublicationStore)
    first = EmbeddingCache(index="cache-a", model="model-a", dimensions=2)
    second = EmbeddingCache(index="cache-b", model="model-b", dimensions=3)
    publications.current.side_effect = [run(first), run(second)]
    service = SimilarBillService(Mock(spec=Elasticsearch), store, publications)

    service.similar("bill", 5)
    service.similar("bill", 5)

    assert [call.kwargs["cache"] for call in store.similar.call_args_list] == [
        first,
        second,
    ]
    assert [call.kwargs["model"] for call in store.similar.call_args_list] == [
        "model-a",
        "model-b",
    ]


@pytest.mark.parametrize("published", [False, True])
def test_legacy_cache_remains_selected_until_a_namespaced_run_is_published(
    published: bool,
) -> None:
    store = Mock(spec=EmbeddingStore, index="legacy")
    store.similar.return_value = EmbeddingNeighbors(source_found=True, neighbors=[])
    publications = Mock(spec=TopicPublicationStore)
    publications.current.return_value = run(None) if published else None
    service = SimilarBillService(
        Mock(spec=Elasticsearch, indices=Mock()), store, publications
    )

    service.similar("bill", 5)

    store.similar.assert_called_once_with(
        "bill",
        5,
        cache=None,
        model="legacy-model" if published else None,
    )


def test_publication_failure_is_not_hidden_by_legacy_cache_fallback() -> None:
    store = Mock(spec=EmbeddingStore)
    publications = Mock(spec=TopicPublicationStore)
    publications.current.side_effect = RuntimeError("publication unavailable")
    with pytest.raises(RuntimeError, match="publication unavailable"):
        SimilarBillService(Mock(spec=Elasticsearch), store, publications).similar(
            "bill", 5
        )
    store.similar.assert_not_called()


def test_manifest_rejects_another_models_cache() -> None:
    specification = run(
        EmbeddingCache(index="a", model="model-a", dimensions=3)
    ).model_dump()
    specification["embedding_model"] = "model-b"
    with pytest.raises(ValidationError, match="cache identity"):
        CompletedTopicRun.model_validate(specification)


def test_embedding_batch_shape_is_verified_before_cache_write() -> None:
    store = Mock(spec=EmbeddingStore, model="model")
    store.fetch_fresh.return_value = {}
    encoder = Mock()
    encoder.get_sentence_embedding_dimension.return_value = 3
    encoder.encode.return_value = np.zeros((1, 4), dtype=np.float32)
    embedder = CachedEmbedder(store, lambda: encoder)

    with pytest.raises(ValueError, match="batch shape"):
        embedder.embed([EmbeddingJob("bill", "text")])
    store.save.assert_not_called()


def test_dimension_drift_is_checked_even_before_all_cache_hits() -> None:
    store = Mock(spec=EmbeddingStore)
    store.ensure_index.side_effect = ValueError("incompatible dimensions")
    encoder = Mock()
    encoder.get_sentence_embedding_dimension.return_value = 4
    with pytest.raises(ValueError, match="incompatible dimensions"):
        CachedEmbedder(store, lambda: encoder).embed([EmbeddingJob("bill", "text")])
    store.fetch_fresh.assert_not_called()
    encoder.encode.assert_not_called()


def test_unknown_dimensions_fail_before_creating_a_cache() -> None:
    store = Mock(spec=EmbeddingStore)
    encoder = Mock()
    encoder.get_sentence_embedding_dimension.return_value = None
    with pytest.raises(ValueError, match="vector dimensions"):
        CachedEmbedder(store, lambda: encoder).embed([EmbeddingJob("bill", "text")])
    store.ensure_index.assert_not_called()
    encoder.encode.assert_not_called()


def test_similarity_filters_candidates_to_the_published_model() -> None:
    client = Mock(spec=Elasticsearch, indices=Mock())
    cache = EmbeddingCache(index="published", model="published-model", dimensions=2)
    client.indices.get_mapping.return_value = {
        cache.index: {"mappings": cache.mappings()}
    }
    client.get.return_value = {
        "_source": {"model": cache.model, "embedding": [1.0, 0.0]}
    }
    client.search.return_value = ObjectApiResponse(
        {"timed_out": False, "_shards": {"failed": 0}, "hits": {"hits": []}}, Mock()
    )

    store = EmbeddingStore(
        client, "configured-not-published", index="legacy", batch_docs=2
    )
    assert store.similar("bill", 5, cache=cache) == EmbeddingNeighbors(
        source_found=True, neighbors=[]
    )

    query = client.search.call_args.kwargs
    assert query["index"] == cache.index
    assert {"term": {"model": cache.model}} in query["knn"]["filter"]["bool"]["filter"]
    assert query["allow_partial_search_results"] is False


@pytest.mark.parametrize("failed_refresh", [False, True])
def test_cache_validation_failure_never_changes_publication(
    failed_refresh: bool,
) -> None:
    client = Mock(spec=Elasticsearch, indices=Mock())
    cache = EmbeddingCache(index="cache", model="model", dimensions=3)
    completed = run(cache)
    client.get.return_value = {"_source": completed.model_dump(mode="json")}
    client.search.return_value = {
        "aggregations": {
            "counts": {
                "buckets": [
                    {"key": kind, "doc_count": count}
                    for kind, count in completed.counts.by_kind().items()
                ]
            }
        }
    }
    client.indices.get_mapping.return_value = {
        cache.index: {"mappings": cache.mappings()}
    }
    if failed_refresh:
        client.indices.refresh.return_value = {"_shards": {"failed": 1}}
    else:
        client.indices.get_mapping.side_effect = RuntimeError("missing cache")
    with pytest.raises(RuntimeError):
        TopicPublicationStore(client, "analysis").publish(completed.model_version, None)
    client.index.assert_not_called()


def test_cache_hit_and_record_model_must_agree() -> None:
    client = Mock(spec=Elasticsearch, indices=Mock())
    client.indices.exists.return_value = True
    client.mget.return_value = {
        "docs": [
            {
                "_id": "bill",
                "found": True,
                "_source": {
                    "model": "wrong",
                    "content_hash": "hash",
                    "embedding": [1.0, 0.0],
                },
            }
        ]
    }
    with pytest.raises(ValueError, match="another model"):
        EmbeddingStore(client, "model", index="cache", batch_docs=2).fetch_fresh(
            {"bill": "hash"}
        )

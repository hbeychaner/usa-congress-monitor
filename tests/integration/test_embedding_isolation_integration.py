import os
from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

import numpy as np
import pytest
from elasticsearch import Elasticsearch

from cdm.backend.services.similar_bill_service import SimilarBillService
from cdm.config.topic_analysis import EmbeddingCache
from cdm.store.embedding_store import EmbeddingRecord, EmbeddingStore
from cdm.store.opensearch import read_alias
from cdm.store.topic_publication import (
    CompletedTopicRun,
    TopicPublicationStore,
    TopicRunCounts,
    TopicRunSpecification,
)
from cdm.utils.cached_embedder import CachedEmbedder, EmbeddingJob


class EmbeddingCluster:
    def __init__(self, client: Elasticsearch, prefix: str) -> None:
        self.client = client
        self.prefix = prefix
        self.analysis = f"{prefix}-analysis"
        self.source = f"{prefix}-source"
        self.indexes: set[str] = {self.analysis, self.source}
        self.publications = TopicPublicationStore(client, self.analysis)

    def store(self, model: str, dimensions: int) -> EmbeddingStore:
        index = EmbeddingStore.namespace(self.prefix, model)
        self.indexes.add(index)
        store = EmbeddingStore(self.client, model, index=index, batch_docs=2)
        store.ensure_index(dimensions)
        return store

    def reference(self, store: EmbeddingStore, dimensions: int) -> EmbeddingCache:
        return EmbeddingCache(
            index=store.index, model=store.model, dimensions=dimensions
        )

    def seed(self, store: EmbeddingStore, neighbor: str, dimensions: int) -> None:
        store.save(
            [
                EmbeddingRecord(
                    doc_id=doc_id,
                    model=store.model,
                    content_hash=store.content_hash(doc_id),
                    embedding=vector,
                )
                for doc_id, vector in [
                    ("bill", [1.0] + [0.0] * (dimensions - 1)),
                    (neighbor, [0.9, 0.1] + [0.0] * (dimensions - 2)),
                ]
            ]
        )

    def write(self, version: str, cache: EmbeddingCache) -> None:
        specification = TopicRunSpecification(
            model_version=version,
            trained_at=datetime.now(UTC),
            embedding_model=cache.model,
            embedding_cache=cache,
            min_congress=113,
            corpus_size=1,
            dated_documents=0,
            model_path=f"test-models/{version}",
            counts=TopicRunCounts(
                topics=1,
                assignments=1,
                metasubjects=1,
                over_time=0,
                metasubject_over_time=0,
            ),
        )
        self.publications.write(
            specification,
            (
                {
                    "_index": self.analysis,
                    "_id": f"{kind}:{version}",
                    "kind": kind,
                    "model_version": version,
                }
                for kind, count in specification.counts.by_kind().items()
                if count
            ),
        )

    def publish(self, version: str, cache: EmbeddingCache) -> CompletedTopicRun:
        baseline = self.publications.snapshot()
        self.write(version, cache)
        return self.publications.publish(version, baseline)

    def source_records(self) -> None:
        self.client.indices.create(
            index=self.source,
            aliases={read_alias("bill"): {}},
        )
        for doc_id in ("bill", "neighbor-a", "neighbor-b"):
            self.client.index(
                index=self.source,
                id=doc_id,
                document={"source_type": "bill", "congress": 119, "title": doc_id},
            )


@pytest.fixture
def cluster() -> Iterator[EmbeddingCluster]:
    url = os.environ.get("EMBEDDING_ISOLATION_TEST_URL")
    if not url:
        pytest.skip("Set EMBEDDING_ISOLATION_TEST_URL to isolated Elasticsearch")
    client = Elasticsearch(url, request_timeout=30, max_retries=0)
    cluster = EmbeddingCluster(client, f"embedding-isolation-test-{uuid4().hex}")
    try:
        yield cluster
    finally:
        for index in cluster.indexes:
            client.indices.delete(index=index, ignore_unavailable=True)
        client.close()


def test_different_models_and_dimensions_keep_their_own_vectors(
    cluster: EmbeddingCluster,
) -> None:
    first = cluster.store("model-a", 2)
    second = cluster.store("model-b", 3)
    cluster.seed(first, "neighbor-a", 2)
    cluster.seed(second, "neighbor-b", 3)

    first_vectors = first.fetch_fresh({"bill": first.content_hash("bill")})
    second_vectors = second.fetch_fresh({"bill": second.content_hash("bill")})
    assert first_vectors["bill"].shape == (2,)
    assert second_vectors["bill"].shape == (3,)
    assert (
        cluster.client.get(index=first.index, id="neighbor-a")["_source"]["model"]
        == "model-a"
    )
    assert (
        cluster.client.get(index=second.index, id="neighbor-b")["_source"]["model"]
        == "model-b"
    )


def test_warming_alternate_model_does_not_change_serving_until_publication(
    cluster: EmbeddingCluster,
) -> None:
    cluster.source_records()
    first = cluster.store("model-a", 2)
    cluster.seed(first, "neighbor-a", 2)
    cluster.publish("run-a", cluster.reference(first, 2))
    service = SimilarBillService(cluster.client, first, cluster.publications)
    assert service.similar("bill", 1).similar[0].bill_id == "neighbor-a"

    second = cluster.store("model-b", 3)
    cluster.client.indices.put_settings(
        index=second.index, settings={"index.refresh_interval": "-1"}
    )
    cluster.seed(second, "neighbor-b", 3)
    assert service.similar("bill", 1).similar[0].bill_id == "neighbor-a"

    cluster.publish("run-b", cluster.reference(second, 3))
    assert service.similar("bill", 1).similar[0].bill_id == "neighbor-b"
    cluster.publications.publish("run-a", cluster.publications.snapshot())
    assert service.similar("bill", 1).similar[0].bill_id == "neighbor-a"
    assert cluster.client.get(index=cluster.source, id="bill")["_source"] == {
        "source_type": "bill",
        "congress": 119,
        "title": "bill",
    }


def test_legacy_cache_remains_intact_through_first_namespaced_publication(
    cluster: EmbeddingCluster,
) -> None:
    cluster.source_records()
    legacy_index = f"{cluster.prefix}-legacy"
    cluster.indexes.add(legacy_index)
    legacy_cache = EmbeddingCache(
        index=legacy_index, model="legacy-model", dimensions=2
    )
    mappings = legacy_cache.mappings()
    del mappings["_meta"]
    cluster.client.indices.create(index=legacy_index, mappings=mappings)
    legacy = EmbeddingStore(
        cluster.client, "legacy-model", index=legacy_index, batch_docs=2
    )
    cluster.seed(legacy, "neighbor-a", 2)
    cluster.client.indices.refresh(index=legacy.index)
    original = cluster.client.get(index=legacy.index, id="bill")["_source"]
    service = SimilarBillService(cluster.client, legacy, cluster.publications)
    assert service.similar("bill", 1).similar[0].bill_id == "neighbor-a"

    fresh = cluster.store("fresh-model", 3)
    cluster.seed(fresh, "neighbor-b", 3)
    assert service.similar("bill", 1).similar[0].bill_id == "neighbor-a"
    cluster.publish("fresh-run", cluster.reference(fresh, 3))
    assert service.similar("bill", 1).similar[0].bill_id == "neighbor-b"
    assert cluster.client.get(index=legacy.index, id="bill")["_source"] == original


def test_same_model_dimension_drift_fails_before_using_cached_vectors(
    cluster: EmbeddingCluster,
) -> None:
    store = cluster.store("model", 2)
    cluster.seed(store, "neighbor-a", 2)
    encoder = Mock()
    encoder.get_sentence_embedding_dimension.return_value = 3
    with pytest.raises(ValueError, match="embedding cache"):
        CachedEmbedder(store, lambda: encoder).embed([EmbeddingJob("bill", "bill")])
    encoder.encode.assert_not_called()
    assert np.array_equal(
        store.fetch_fresh({"bill": store.content_hash("bill")})["bill"],
        np.array([1.0, 0.0], dtype=np.float32),
    )


def test_another_models_vector_cannot_be_written(cluster: EmbeddingCluster) -> None:
    store = cluster.store("model", 2)
    with pytest.raises(ValueError, match="another model"):
        store.save(
            [
                EmbeddingRecord(
                    doc_id="wrong",
                    model="other",
                    content_hash="hash",
                    embedding=[1.0, 0.0],
                )
            ]
        )
    assert not cluster.client.exists(index=store.index, id="wrong")


def test_corrupt_target_cache_cannot_replace_current_publication(
    cluster: EmbeddingCluster,
) -> None:
    first = cluster.store("model-a", 2)
    cluster.seed(first, "neighbor-a", 2)
    original = cluster.publish("run-a", cluster.reference(first, 2))
    second = cluster.store("model-b", 3)
    cluster.seed(second, "neighbor-b", 3)
    cluster.write("run-b", cluster.reference(second, 3))
    cluster.client.indices.put_mapping(
        index=second.index, meta={"embedding_model": "unrelated-model"}
    )
    with pytest.raises(ValueError, match="embedding cache"):
        cluster.publications.publish("run-b", cluster.publications.snapshot())
    assert cluster.publications.current() == original

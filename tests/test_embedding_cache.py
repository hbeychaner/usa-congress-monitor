from __future__ import annotations

from unittest.mock import Mock

import numpy as np
import pytest
from elasticsearch import Elasticsearch

from cdm.store.embedding_store import EmbeddingRecord, EmbeddingStore
from cdm.utils.cached_embedder import CachedEmbedder, EmbeddingJob

DIMS = 3


class InMemoryStore(EmbeddingStore):
    def __init__(self) -> None:
        super().__init__(client=None, model="test-model", index="test", batch_docs=8)
        self.records: dict[str, EmbeddingRecord] = {}

    def ensure_index(self, dims: int) -> None:
        assert dims == DIMS

    def fetch_fresh(self, expected: dict[str, str]) -> dict[str, np.ndarray]:
        return {
            doc_id: np.asarray(record.embedding, dtype=np.float32)
            for doc_id, record in self.records.items()
            if expected.get(doc_id) == record.content_hash
        }

    def save(self, records) -> None:
        for record in records:
            self.records[record.doc_id] = record


class CountingEmbedder:
    def __init__(self) -> None:
        self.encoded: list[str] = []

    def get_sentence_embedding_dimension(self) -> int:
        return DIMS

    def encode(self, texts: list[str], show_progress_bar: bool = False) -> np.ndarray:
        self.encoded.extend(texts)
        return np.array([[len(text), 1.0, 2.0] for text in texts], dtype=np.float32)


def test_only_new_or_changed_texts_are_encoded() -> None:
    store = InMemoryStore()
    embedder = CountingEmbedder()
    cached = CachedEmbedder(store, lambda: embedder, chunk_size=2)
    jobs = [EmbeddingJob("a", "alpha"), EmbeddingJob("b", "bb"), EmbeddingJob("c", "c")]

    first = cached.embed(jobs)
    assert embedder.encoded == ["alpha", "bb", "c"]

    embedder.encoded.clear()
    jobs[1] = EmbeddingJob("b", "changed")
    second = cached.embed(jobs)

    assert embedder.encoded == ["changed"]
    assert second.shape == (3, DIMS)
    assert np.array_equal(second[0], first[0])
    assert second[1][0] == len("changed")


def test_progress_reaches_one_and_counts_cache_hits() -> None:
    store = InMemoryStore()
    cached = CachedEmbedder(store, CountingEmbedder, chunk_size=1)
    jobs = [EmbeddingJob("a", "x"), EmbeddingJob("b", "y")]
    cached.embed(jobs[:1])

    seen: list[float] = []
    cached.embed(jobs, seen.append)

    assert seen[0] == 0.5
    assert seen[-1] == 1.0


def test_hash_depends_on_model() -> None:
    first = EmbeddingStore(None, "m1", index="i", batch_docs=1).content_hash("text")
    second = EmbeddingStore(None, "m2", index="i", batch_docs=1).content_hash("text")
    assert first != second


def test_cache_batches_keep_only_fresh_vectors() -> None:
    client = Mock(spec=Elasticsearch)
    client.indices = Mock()
    client.indices.exists.return_value = True
    client.mget.side_effect = [
        {
            "docs": [
                {
                    "_id": "a",
                    "found": True,
                    "_source": {
                        "model": "test-model",
                        "content_hash": "fresh",
                        "embedding": [1.0, 2.0, 3.0],
                    },
                },
                {"_id": "b", "found": False},
            ]
        },
        {
            "docs": [
                {
                    "_id": "c",
                    "found": True,
                    "_source": {"content_hash": "stale", "embedding": [3.0, 2.0, 1.0]},
                }
            ]
        },
    ]
    store = EmbeddingStore(client, "test-model", index="test", batch_docs=2)

    fresh = store.fetch_fresh({"a": "fresh", "b": "missing", "c": "expected"})

    assert list(fresh) == ["a"]
    assert np.array_equal(fresh["a"], np.array([1.0, 2.0, 3.0], dtype=np.float32))
    assert [call.kwargs["ids"] for call in client.mget.call_args_list] == [
        ("a", "b"),
        ("c",),
    ]
    assert [call[0] for call in client.method_calls] == [
        "indices.exists",
        "mget",
        "mget",
    ]


@pytest.mark.parametrize(("model", "dims"), [("wrong-model", DIMS), ("test-model", 4)])
def test_existing_incompatible_cache_is_rejected(model: str, dims: int) -> None:
    client = Mock(spec=Elasticsearch, indices=Mock())
    client.indices.exists.return_value = True
    client.indices.get_mapping.return_value = {
        "test": {
            "mappings": {
                "_meta": {"embedding_model": model},
                "properties": {"embedding": {"type": "dense_vector", "dims": dims}},
            }
        }
    }

    with pytest.raises(ValueError, match="embedding cache"):
        EmbeddingStore(client, "test-model", index="test", batch_docs=2).ensure_index(
            DIMS
        )
    client.indices.create.assert_not_called()

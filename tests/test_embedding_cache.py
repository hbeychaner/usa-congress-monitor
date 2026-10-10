from __future__ import annotations

import numpy as np

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

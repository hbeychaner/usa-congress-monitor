"""Embeds documents through a persistent cache so unchanged bills are never re-encoded."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from cdm.store.embedding_store import EmbeddingRecord, EmbeddingStore

EMBED_CHUNK_SIZE = 2048


@dataclass(frozen=True)
class EmbeddingJob:
    doc_id: str
    text: str


class CachedEmbedder:
    """Encodes only cache misses, persisting each chunk so a crashed run resumes."""

    def __init__(
        self,
        store: EmbeddingStore,
        embedder_factory: Callable[[], Any],
        chunk_size: int = EMBED_CHUNK_SIZE,
    ) -> None:
        self.store = store
        self.embedder_factory = embedder_factory
        self.chunk_size = chunk_size

    def embed(
        self,
        jobs: Sequence[EmbeddingJob],
        on_progress: Callable[[float], None] | None = None,
    ) -> np.ndarray:
        hashes = {job.doc_id: self.store.content_hash(job.text) for job in jobs}
        vectors = self.store.fetch_fresh(hashes)
        misses = [job for job in jobs if job.doc_id not in vectors]
        done = len(jobs) - len(misses)
        self._report(on_progress, done, len(jobs))
        for start in range(0, len(misses), self.chunk_size):
            chunk = misses[start : start + self.chunk_size]
            encoded = self.embedder_factory().encode(
                [job.text for job in chunk], show_progress_bar=False
            )
            self.store.ensure_index(encoded.shape[1])
            self.store.save(
                EmbeddingRecord(
                    doc_id=job.doc_id,
                    model=self.store.model,
                    content_hash=hashes[job.doc_id],
                    embedding=vector.tolist(),
                )
                for job, vector in zip(chunk, encoded)
            )
            for job, vector in zip(chunk, encoded):
                vectors[job.doc_id] = vector
            done += len(chunk)
            self._report(on_progress, done, len(jobs))
        return np.vstack([vectors[job.doc_id] for job in jobs])

    @staticmethod
    def _report(
        on_progress: Callable[[float], None] | None, done: int, total: int
    ) -> None:
        if on_progress and total:
            on_progress(min(1.0, done / total))

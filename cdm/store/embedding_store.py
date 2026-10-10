"""Elasticsearch-backed cache of bill embeddings, also used for similar-bill search."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from enum import StrEnum

import numpy as np
from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch.helpers import bulk, scan
from pydantic import BaseModel, Field

from cdm.utils.json_types import JsonObject

KNN_CANDIDATE_FACTOR = 10


class EmbeddingField(StrEnum):
    MODEL = "model"
    CONTENT_HASH = "content_hash"
    EMBEDDING = "embedding"
    EMBEDDED_AT = "embedded_at"


class EmbeddingRecord(BaseModel):
    """One bill's vector, valid only while its text hash and model still match."""

    doc_id: str
    model: str
    content_hash: str
    embedding: list[float]
    embedded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SimilarDocument(BaseModel):
    doc_id: str
    score: float


class PruneReport(BaseModel):
    deleted: int = 0


def _batches(items: list[str], size: int) -> Iterator[list[str]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


class EmbeddingStore:
    """Reads, writes, prunes, and searches the embeddings index for one model."""

    def __init__(
        self,
        client: Elasticsearch,
        model: str,
        *,
        index: str,
        batch_docs: int,
    ) -> None:
        self.client = client
        self.model = model
        self.index = index
        self.batch_docs = batch_docs

    def content_hash(self, text: str) -> str:
        """Hash of model + text, so changing either invalidates the cached vector."""
        digest = hashlib.sha256(f"{self.model}\0{text}".encode())
        return digest.hexdigest()

    def ensure_index(self, dims: int) -> None:
        if self.client.indices.exists(index=self.index):
            return
        self.client.indices.create(
            index=self.index,
            mappings={
                "properties": {
                    EmbeddingField.MODEL: {"type": "keyword"},
                    EmbeddingField.CONTENT_HASH: {"type": "keyword", "index": False},
                    EmbeddingField.EMBEDDED_AT: {"type": "date"},
                    EmbeddingField.EMBEDDING: {
                        "type": "dense_vector",
                        "dims": dims,
                        "index": True,
                        "similarity": "cosine",
                    },
                }
            },
        )

    def fetch_fresh(self, expected: dict[str, str]) -> dict[str, np.ndarray]:
        """Return cached vectors whose stored hash equals the expected hash."""
        fresh: dict[str, np.ndarray] = {}
        if not self.client.indices.exists(index=self.index):
            return fresh
        for ids in _batches(list(expected), self.batch_docs):
            response = self.client.mget(
                index=self.index,
                ids=ids,
                source_includes=[EmbeddingField.CONTENT_HASH, EmbeddingField.EMBEDDING],
            )
            for doc in response["docs"]:
                source = doc.get("_source") if doc.get("found") else None
                if (
                    source
                    and source[EmbeddingField.CONTENT_HASH] == expected[doc["_id"]]
                ):
                    fresh[doc["_id"]] = np.asarray(
                        source[EmbeddingField.EMBEDDING], dtype=np.float32
                    )
        return fresh

    def save(self, records: Iterable[EmbeddingRecord]) -> None:
        def actions() -> Iterator[JsonObject]:
            for record in records:
                yield {
                    "_index": self.index,
                    "_id": record.doc_id,
                    **record.model_dump(mode="json", exclude={"doc_id"}),
                }

        bulk(self.client, actions(), chunk_size=self.batch_docs)

    def prune(self, keep_ids: set[str]) -> PruneReport:
        """Delete vectors for bills outside ``keep_ids`` or from another model."""
        report = PruneReport()
        if not self.client.indices.exists(index=self.index):
            return report
        stale: list[str] = []
        for hit in scan(
            self.client,
            index=self.index,
            query={"query": {"match_all": {}}, "_source": [EmbeddingField.MODEL]},
        ):
            other_model = hit["_source"].get(EmbeddingField.MODEL) != self.model
            if other_model or hit["_id"] not in keep_ids:
                stale.append(hit["_id"])
        for ids in _batches(stale, self.batch_docs):
            bulk(
                self.client,
                ({"_op_type": "delete", "_index": self.index, "_id": i} for i in ids),
                raise_on_error=False,
            )
        report.deleted = len(stale)
        return report

    def similar(self, doc_id: str, size: int) -> list[SimilarDocument]:
        """Nearest bills by cosine similarity, excluding the bill itself."""
        try:
            got = self.client.get(
                index=self.index,
                id=doc_id,
                source_includes=[EmbeddingField.EMBEDDING],
            )
        except NotFoundError:
            return []
        response = self.client.search(
            index=self.index,
            size=size,
            source=False,
            knn={
                "field": EmbeddingField.EMBEDDING,
                "query_vector": got["_source"][EmbeddingField.EMBEDDING],
                "k": size,
                "num_candidates": size * KNN_CANDIDATE_FACTOR,
                "filter": {"bool": {"must_not": [{"ids": {"values": [doc_id]}}]}},
            },
        )
        return [
            SimilarDocument(doc_id=hit["_id"], score=float(hit["_score"]))
            for hit in response["hits"]["hits"]
        ]

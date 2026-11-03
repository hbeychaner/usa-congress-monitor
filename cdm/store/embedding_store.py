"""Elasticsearch-backed cache of bill embeddings, also used for similar-bill search."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from enum import StrEnum
from itertools import batched

import numpy as np
from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch.helpers import bulk
from pydantic import BaseModel, Field

from cdm.config.topic_analysis import EmbeddingCache, EmbeddingSearchConfig
from cdm.store.client import SearchCompletion
from cdm.utils.json_types import JsonObject


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


class EmbeddingNeighbors(BaseModel):
    source_found: bool
    neighbors: list[SimilarDocument]


class EmbeddingStore:
    """Reads, writes, and searches the embeddings index for one model."""

    def __init__(
        self,
        client: Elasticsearch,
        model: str,
        *,
        index: str,
        batch_docs: int,
        settings: EmbeddingSearchConfig | None = None,
    ) -> None:
        self.client = client
        self.model = model
        self.index = index
        self.batch_docs = batch_docs
        self._settings = settings or EmbeddingSearchConfig()

    def content_hash(self, text: str) -> str:
        """Hash of model + text, so changing either invalidates the cached vector."""
        digest = hashlib.sha256(f"{self.model}\0{text}".encode())
        return digest.hexdigest()

    @staticmethod
    def namespace(base_index: str, model: str) -> str:
        return f"{base_index}-{hashlib.sha256(model.encode()).hexdigest()}"

    def ensure_index(self, dims: int) -> None:
        cache = EmbeddingCache(index=self.index, model=self.model, dimensions=dims)
        if self.client.indices.exists(index=self.index):
            cache.verify_mapping(
                self.client.indices.get_mapping(index=self.index)[self.index][
                    "mappings"
                ]
            )
        else:
            self.client.indices.create(index=self.index, mappings=cache.mappings())

    def fetch_fresh(self, expected: dict[str, str]) -> dict[str, np.ndarray]:
        """Return cached vectors whose stored hash equals the expected hash."""
        fresh: dict[str, np.ndarray] = {}
        if not self.client.indices.exists(index=self.index):
            return fresh
        for ids in batched(expected, self.batch_docs):
            response = self.client.mget(
                index=self.index,
                ids=ids,
                source_includes=[
                    EmbeddingField.MODEL,
                    EmbeddingField.CONTENT_HASH,
                    EmbeddingField.EMBEDDING,
                ],
            )
            for doc in response["docs"]:
                source = doc.get("_source") if doc.get("found") else None
                if (
                    source
                    and source[EmbeddingField.CONTENT_HASH] == expected[doc["_id"]]
                ):
                    if source[EmbeddingField.MODEL] != self.model:
                        raise ValueError(
                            "Embedding cache contains a vector from another model"
                        )
                    fresh[doc["_id"]] = np.asarray(
                        source[EmbeddingField.EMBEDDING], dtype=np.float32
                    )
        return fresh

    def save(self, records: Iterable[EmbeddingRecord]) -> None:
        def actions() -> Iterator[JsonObject]:
            for record in records:
                if record.model != self.model:
                    raise ValueError(
                        "Cannot write another model's vector to this embedding cache"
                    )
                yield {
                    "_index": self.index,
                    "_id": record.doc_id,
                    **record.model_dump(mode="json", exclude={"doc_id"}),
                }

        bulk(self.client, actions(), chunk_size=self.batch_docs)

    def similar(
        self,
        doc_id: str,
        size: int,
        *,
        cache: EmbeddingCache | None = None,
        model: str | None = None,
    ) -> EmbeddingNeighbors:
        """Nearest bills by cosine similarity, excluding the bill itself."""
        index = cache.index if cache else self.index
        model = cache.model if cache else (model or self.model)
        if cache:
            cache.verify_mapping(
                self.client.indices.get_mapping(index=index)[index]["mappings"]
            )
        try:
            got = self.client.get(
                index=index,
                id=doc_id,
                source_includes=[EmbeddingField.MODEL, EmbeddingField.EMBEDDING],
            )
        except NotFoundError as exc:
            if isinstance(exc.body, dict) and exc.body.get("found") is False:
                return EmbeddingNeighbors(source_found=False, neighbors=[])
            raise
        if got["_source"][EmbeddingField.MODEL] != model:
            raise ValueError("Embedding cache contains a vector from another model")
        response = self.client.search(
            index=index,
            size=size,
            source=False,
            allow_partial_search_results=False,
            knn={
                "field": EmbeddingField.EMBEDDING,
                "query_vector": got["_source"][EmbeddingField.EMBEDDING],
                "k": size,
                "num_candidates": size * self._settings.candidate_factor,
                "filter": {
                    "bool": {
                        "filter": [{"term": {EmbeddingField.MODEL: model}}],
                        "must_not": [{"ids": {"values": [doc_id]}}],
                    }
                },
            },
        )
        SearchCompletion.model_validate(response.body).require_complete()
        return EmbeddingNeighbors(
            source_found=True,
            neighbors=[
                SimilarDocument(doc_id=hit["_id"], score=float(hit["_score"]))
                for hit in response["hits"]["hits"]
            ],
        )

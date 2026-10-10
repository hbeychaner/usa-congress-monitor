"""Nearest-neighbour bills from the stored embeddings."""

from __future__ import annotations

from elasticsearch import Elasticsearch

from cdm.contracts.api import SimilarBill, SimilarBillsResponse
from cdm.store.embedding_store import EmbeddingStore
from cdm.store.opensearch import read_alias


class SimilarBillService:
    def __init__(self, client: Elasticsearch, store: EmbeddingStore) -> None:
        self.client = client
        self.store = store

    def similar(self, bill_id: str, size: int) -> SimilarBillsResponse:
        neighbours = self.store.similar(bill_id, size)
        if not neighbours:
            return SimilarBillsResponse(bill_id=bill_id)
        docs = self.client.mget(
            index=read_alias("bill"),
            ids=[n.doc_id for n in neighbours],
            source_includes=["title", "congress"],
        )["docs"]
        sources = {d["_id"]: d["_source"] for d in docs if d.get("found")}
        return SimilarBillsResponse(
            bill_id=bill_id,
            similar=[
                SimilarBill(
                    bill_id=n.doc_id,
                    title=str(sources[n.doc_id].get("title") or n.doc_id),
                    congress=sources[n.doc_id].get("congress"),
                    score=n.score,
                )
                for n in neighbours
                if n.doc_id in sources
            ],
        )

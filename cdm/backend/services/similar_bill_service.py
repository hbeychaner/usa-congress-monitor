"""Nearest-neighbour bills from the stored embeddings."""

from __future__ import annotations

from elasticsearch import Elasticsearch

from cdm.contracts.analysis import AnalysisState, AnalysisStatus
from cdm.contracts.api import SimilarBill, SimilarBillsResponse
from cdm.store.client import IncompleteSearchError
from cdm.store.embedding_store import EmbeddingStore
from cdm.store.opensearch import read_alias
from cdm.store.topic_publication import TopicPublicationStore


class SimilarBillService:
    def __init__(
        self,
        client: Elasticsearch,
        store: EmbeddingStore,
        publications: TopicPublicationStore,
    ) -> None:
        self.client = client
        self.store = store
        self.publications = publications

    def similar(self, bill_id: str, size: int) -> SimilarBillsResponse:
        run = self.publications.current()
        if run is None and not self.client.indices.exists(index=self.store.index):
            return SimilarBillsResponse(
                bill_id=bill_id, analysis=AnalysisStatus(state=AnalysisState.NOT_BUILT)
            )
        result = self.store.similar(
            bill_id,
            size,
            cache=run.embedding_cache if run else None,
            model=run.embedding_model if run else None,
        )
        neighbours = result.neighbors
        if not neighbours:
            analysis = (
                AnalysisStatus.for_model(run.model_version, run.model_version, False)
                if run
                else AnalysisStatus(state=AnalysisState.UNKNOWN)
            )
            if not result.source_found:
                analysis.state = AnalysisState.NOT_BUILT
            return SimilarBillsResponse(
                bill_id=bill_id,
                analysis=analysis,
            )
        docs = self.client.mget(
            index=read_alias("bill"),
            ids=[n.doc_id for n in neighbours],
            source_includes=["title", "congress"],
        )["docs"]
        if any("error" in doc for doc in docs):
            raise IncompleteSearchError("Similar bill lookup failed")
        sources = {d["_id"]: d["_source"] for d in docs if d.get("found")}
        similar = [
            SimilarBill(
                bill_id=n.doc_id,
                title=str(sources[n.doc_id].get("title") or n.doc_id),
                congress=sources[n.doc_id].get("congress"),
                score=n.score,
            )
            for n in neighbours
            if n.doc_id in sources
        ]
        return SimilarBillsResponse(
            bill_id=bill_id,
            similar=similar,
            analysis=AnalysisStatus.for_model(
                run.model_version, run.model_version, bool(similar)
            )
            if run
            else AnalysisStatus(state=AnalysisState.UNKNOWN),
        )

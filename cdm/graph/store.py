"""Reads bill signatures and reads/writes the versioned graph index."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from itertools import batched
from typing import Any

from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch.helpers import scan

from cdm.graph.models import (
    BillSignature,
    DocumentKind,
    GraphField,
    GraphVersionPointer,
    MemberEdge,
    RollCallVotes,
    Signal,
)
from cdm.store.index_manager import IndexManager
from cdm.store.opensearch import bulk_upsert, index_name, read_alias

GRAPH_INDEX = "analysis_graph"
KEEP_VERSIONS = 3
WRITE_BATCH = 5000
FIRST_CONGRESS = 113


class BillSignatureReader:
    """Streams sponsor/cosponsor ids for bills from the legislation index."""

    def __init__(self, client: Elasticsearch, first_congress: int = FIRST_CONGRESS):
        self.client = client
        self.first_congress = first_congress

    def read(self) -> Iterator[BillSignature]:
        fields = [
            field.alias or name for name, field in BillSignature.model_fields.items()
        ]
        hits = scan(
            self.client,
            index=read_alias("bill"),
            query={
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"source_type": "bill"}},
                            {"range": {"congress": {"gte": self.first_congress}}},
                        ]
                    }
                },
                "_source": fields,
            },
        )
        for hit in hits:
            yield BillSignature.model_validate(hit["_source"])


class RollCallReader:
    """Streams yea/nay voter ids for roll calls from the roll call index."""

    def __init__(self, client: Elasticsearch, first_congress: int = FIRST_CONGRESS):
        self.client = client
        self.first_congress = first_congress

    def read(self) -> Iterator[RollCallVotes]:
        hits = scan(
            self.client,
            index=read_alias("rollcall"),
            query={
                "query": {"range": {"congress": {"gte": self.first_congress}}},
                "_source": list(RollCallVotes.model_fields),
            },
        )
        for hit in hits:
            yield RollCallVotes.model_validate(hit["_source"])


class GraphStore:
    """Writes edges under a version and flips the per-signal pointer when done."""

    def __init__(self, client: Elasticsearch) -> None:
        self.client = client
        self.index = index_name(GRAPH_INDEX)

    def ensure_index(self) -> None:
        IndexManager(self.client).create(GRAPH_INDEX)

    def write_edges(self, edges: Iterable[MemberEdge]) -> int:
        written = 0
        for batch in batched(edges, WRITE_BATCH):
            result = bulk_upsert(
                self.client,
                GRAPH_INDEX,
                (edge.model_dump(mode="json") for edge in batch),
                replace=True,
            )
            if result.get("errors"):
                raise RuntimeError(f"graph bulk errors: {result.get('error_details')}")
            written += int(result["updated"])
        return written

    def publish(self, signal: Signal, graph_version: str) -> None:
        pointer = GraphVersionPointer(signal=signal, graph_version=graph_version)
        self.client.index(
            index=self.index,
            id=pointer.id,
            document=pointer.model_dump(mode="json"),
            refresh=True,
        )

    def active_version(self, signal: Signal) -> str | None:
        try:
            response = self.client.get(
                index=self.index, id=GraphVersionPointer.pointer_id(signal)
            )
        except NotFoundError:
            return None
        source: dict[str, Any] = response["_source"]
        return source.get(GraphField.GRAPH_VERSION)

    def prune(self, signal: Signal) -> list[str]:
        """Delete edges of all but the newest versions for the signal."""
        response = self.client.search(
            index=self.index,
            size=0,
            query={
                "bool": {
                    "filter": [
                        {"term": {GraphField.KIND: DocumentKind.EDGE}},
                        {"term": {GraphField.SIGNAL: signal}},
                    ]
                }
            },
            aggs={"versions": {"terms": {"field": GraphField.GRAPH_VERSION, "size": 100}}},
        )
        versions = sorted(
            (bucket["key"] for bucket in response["aggregations"]["versions"]["buckets"]),
            reverse=True,
        )
        stale = versions[KEEP_VERSIONS:]
        if stale:
            self.client.delete_by_query(
                index=self.index,
                query={
                    "bool": {
                        "filter": [
                            {"term": {GraphField.SIGNAL: signal}},
                            {"terms": {GraphField.GRAPH_VERSION: stale}},
                        ]
                    }
                },
                conflicts="proceed",
                wait_for_completion=False,
            )
        return stale

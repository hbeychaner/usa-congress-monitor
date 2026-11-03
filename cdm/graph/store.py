"""Reads bill signatures and reads/writes the versioned graph index."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from itertools import batched

from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch.helpers import scan
from pydantic import TypeAdapter

from cdm.config.topic_analysis import GraphStoreConfig
from cdm.graph.models import (
    BillSignature,
    DocumentKind,
    GraphField,
    GraphIndexDefinition,
    GraphMapping,
    GraphVersionPointer,
    MemberEdge,
    RollCallVotes,
    Signal,
)
from cdm.store.index_manager import IndexManager, load_definitions
from cdm.store.opensearch import bulk_upsert, index_name, read_alias


class BillSignatureReader:
    """Streams sponsor/cosponsor ids for bills from the legislation index."""

    def __init__(
        self, client: Elasticsearch, settings: GraphStoreConfig | None = None
    ) -> None:
        self.client = client
        self.first_congress = (settings or GraphStoreConfig()).first_congress

    def read(self) -> Iterator[BillSignature]:
        fields = [
            field.alias or name for name, field in BillSignature.model_fields.items()
        ]
        hits = scan(
            self.client,
            index=read_alias("bill"),
            allow_partial_search_results=False,
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

    def __init__(
        self,
        client: Elasticsearch,
        settings: GraphStoreConfig | None = None,
        *,
        index: str | None = None,
    ) -> None:
        self.client = client
        self.first_congress = (settings or GraphStoreConfig()).first_congress
        self.index = index or read_alias("rollcall")

    def read(self) -> Iterator[RollCallVotes]:
        hits = scan(
            self.client,
            index=self.index,
            allow_partial_search_results=False,
            query={
                "query": {"range": {"congress": {"gte": self.first_congress}}},
                "_source": list(RollCallVotes.model_fields),
            },
        )
        for hit in hits:
            roll = RollCallVotes.model_validate(hit["_source"])
            if not any(
                (roll.yea_ids, roll.nay_ids, roll.present_ids, roll.not_voting_ids)
            ):
                raise ValueError(
                    f"Roll call {hit['_id']} has no linked member positions"
                )
            yield roll


class GraphStore:
    """Writes edges under a version and flips the per-signal pointer when done."""

    def __init__(
        self, client: Elasticsearch, settings: GraphStoreConfig | None = None
    ) -> None:
        self.client = client
        self._settings = settings or GraphStoreConfig()
        self.index = index_name(self._settings.index)

    def ensure_index(self) -> None:
        if self.client.indices.exists(index=self.index):
            self.require_schema()
            return
        IndexManager(self.client).create(self._settings.index)
        self.require_schema()

    def schema_errors(self) -> list[str]:
        try:
            response = self.client.indices.get_mapping(index=self.index)
        except NotFoundError:
            return [f"{self.index}: missing graph index"]
        definitions = TypeAdapter(dict[str, GraphIndexDefinition]).validate_python(
            response.body
        )
        if not definitions:
            raise ValueError(f"No graph mapping returned for {self.index}")
        expected = GraphMapping.model_validate(
            load_definitions()["analysis_graph"]["mappings"]
        )
        return [
            f"{index}: {problem}"
            for index, definition in definitions.items()
            for problem in expected.differences(definition.mappings)
        ]

    def require_schema(self) -> None:
        problems = self.schema_errors()
        if problems:
            raise ValueError(
                f"Incompatible graph index; approved schema migration required: {problems}"
            )

    def write_edges(self, edges: Iterable[MemberEdge]) -> int:
        self.require_schema()
        written = 0
        for batch in batched(edges, self._settings.write_batch):
            result = bulk_upsert(
                self.client,
                self._settings.index,
                (edge.model_dump(mode="json") for edge in batch),
                replace=True,
                target_index=self.index,
            )
            written += int(result["updated"])
        return written

    def publish(self, pointer: GraphVersionPointer) -> None:
        self.require_schema()
        refreshed = self.client.indices.refresh(index=self.index)
        if refreshed["_shards"]["failed"]:
            raise RuntimeError(f"Graph refresh failed: {refreshed['_shards']}")
        self.client.index(
            index=self.index,
            id=pointer.id,
            document=pointer.model_dump(mode="json"),
            refresh=True,
        )

    def active_pointer(self, signal: Signal) -> GraphVersionPointer | None:
        try:
            response = self.client.get(
                index=self.index, id=GraphVersionPointer.pointer_id(signal)
            )
        except NotFoundError:
            return None
        return GraphVersionPointer.model_validate(response["_source"])

    def active_version(self, signal: Signal) -> str | None:
        pointer = self.active_pointer(signal)
        return pointer.graph_version if pointer else None

    def edge_count(self, signal: Signal, graph_version: str) -> int:
        response = self.client.count(
            index=self.index,
            query={
                "bool": {
                    "filter": [
                        {"term": {GraphField.KIND: DocumentKind.EDGE}},
                        {"term": {GraphField.SIGNAL: signal}},
                        {"term": {GraphField.GRAPH_VERSION: graph_version}},
                    ]
                }
            },
        )
        return int(response["count"])

"""Reads bill signatures and reads/writes the versioned graph index."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from itertools import batched

from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch.helpers import BulkIndexError, bulk, scan
from pydantic import TypeAdapter

from cdm.config.topic_analysis import GraphStoreConfig
from cdm.graph.models import (
    BillSignature,
    DocumentKind,
    GraphField,
    GraphIndexDefinition,
    GraphMapping,
    GraphPointerSnapshot,
    GraphVersionPointer,
    MemberEdge,
    RollCallVotes,
    Signal,
)
from cdm.store.bill_scope import BillReadScope
from cdm.store.index_manager import IndexManager, load_definitions
from cdm.store.opensearch import index_name, read_alias


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
                            BillReadScope.query(),
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
            try:
                count, _ = bulk(
                    self.client,
                    (
                        {
                            "_op_type": "create",
                            "_index": self.index,
                            "_id": edge.id,
                            "_source": edge.model_dump(mode="json"),
                        }
                        for edge in batch
                    ),
                    raise_on_error=True,
                )
            except BulkIndexError as exc:
                raise RuntimeError("Bulk indexing failed for graph candidate") from exc
            if count != len(batch):
                raise RuntimeError("Graph candidate acknowledgements are incomplete")
            written += count
        return written

    def pointer_snapshot(self, signal: Signal) -> GraphPointerSnapshot:
        try:
            response = self.client.get(
                index=self.index, id=GraphVersionPointer.pointer_id(signal)
            )
        except NotFoundError as exc:
            if isinstance(exc.body, dict) and exc.body.get("found") is False:
                return GraphPointerSnapshot(signal=signal)
            raise
        return GraphPointerSnapshot(
            signal=signal,
            pointer=GraphVersionPointer.model_validate(response["_source"]),
            sequence_number=response["_seq_no"],
            primary_term=response["_primary_term"],
        )

    def publish(
        self,
        pointer: GraphVersionPointer,
        *,
        expected: GraphPointerSnapshot | None = None,
    ) -> None:
        self.require_schema()
        refreshed = self.client.indices.refresh(index=self.index)
        if refreshed["_shards"]["failed"]:
            raise RuntimeError(f"Graph refresh failed: {refreshed['_shards']}")
        before = expected if expected is not None else self.pointer_snapshot(pointer.signal)
        if before.signal != pointer.signal:
            raise ValueError("Cannot publish against another graph signal's snapshot")
        if before.pointer is None:
            self.client.index(
                index=self.index,
                id=pointer.id,
                document=pointer.model_dump(mode="json"),
                op_type="create",
                refresh=True,
            )
        else:
            self.client.index(
                index=self.index,
                id=pointer.id,
                document=pointer.model_dump(mode="json"),
                if_seq_no=before.sequence_number,
                if_primary_term=before.primary_term,
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

"""Reads and writes metasubject documents in the topic analysis index."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from enum import StrEnum

from elasticsearch import Elasticsearch

from cdm.utils.json_types import JsonObject
from cdm.utils.metasubjects import Metasubject, MetasubjectOverTimeRow

MODEL_VERSION_FIELD = "model_version"
LATEST_SCAN_SIZE = 200

METASUBJECT_MAPPINGS: dict[str, dict[str, dict[str, str | bool]]] = {
    "properties": {
        "metasubject_id": {"type": "integer"},
        "metasubject_confidence": {"type": "float"},
        "assigned_by": {"type": "keyword"},
        "low_confidence": {"type": "boolean"},
        "topic_ids": {"type": "integer"},
        "centroid": {"type": "float", "index": False, "doc_values": False},
    }
}


class MetasubjectKind(StrEnum):
    METASUBJECT = "metasubject"
    OVER_TIME = "metasubject_over_time"


class MetasubjectRepository:
    def __init__(self, client: Elasticsearch, index: str) -> None:
        self.client = client
        self.index = index

    def ensure_mappings(self) -> None:
        self.client.indices.put_mapping(
            index=self.index, properties=METASUBJECT_MAPPINGS["properties"]
        )

    def latest(self) -> list[Metasubject]:
        """Metasubjects of the newest model version, or [] when none exist."""
        response = self.client.search(
            index=self.index,
            size=LATEST_SCAN_SIZE,
            query={"term": {"kind": MetasubjectKind.METASUBJECT}},
            sort=[{"trained_at": {"order": "desc"}}],
        )
        hits = response["hits"]["hits"]
        if not hits:
            return []
        newest = hits[0]["_source"][MODEL_VERSION_FIELD]
        return [
            Metasubject.model_validate(hit["_source"])
            for hit in hits
            if hit["_source"][MODEL_VERSION_FIELD] == newest
        ]

    def actions(
        self,
        model_version: str,
        trained_at: str,
        metasubjects: Sequence[Metasubject],
        over_time: Sequence[MetasubjectOverTimeRow],
    ) -> Iterator[JsonObject]:
        common = {MODEL_VERSION_FIELD: model_version, "trained_at": trained_at}
        for group in metasubjects:
            yield {
                "_index": self.index,
                "_id": f"metasubject:{model_version}:{group.metasubject_id}",
                "kind": MetasubjectKind.METASUBJECT,
                **common,
                **group.model_dump(mode="json"),
            }
        for number, row in enumerate(over_time):
            yield {
                "_index": self.index,
                "_id": f"metasubject_over_time:{model_version}:{number}",
                "kind": MetasubjectKind.OVER_TIME,
                **common,
                **row.model_dump(mode="json"),
            }

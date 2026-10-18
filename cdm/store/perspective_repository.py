"""Reads and writes per-topic party perspectives in the topic analysis index."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from enum import StrEnum

from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch.helpers import bulk

from cdm.perspectives.models import TopicPerspectives
from cdm.utils.json_types import JsonObject

MODEL_VERSION_FIELD = "model_version"
BUILT_AT_FIELD = "built_at"
CONGRESS_FIELD = "congress"
TOPIC_FIELD = "topic_id"
SCAN_SIZE = 10000
CONGRESS_BUCKETS = 200

# Nested payloads are only ever read back whole, so they are stored without being indexed.
_STORED = {"type": "object", "enabled": False}
PERSPECTIVE_MAPPINGS: dict[str, dict[str, dict[str, str | bool]]] = {
    "properties": {
        CONGRESS_FIELD: {"type": "integer"},
        BUILT_AT_FIELD: {"type": "date"},
        "party_bills": _STORED,
        "party_terms": _STORED,
        "bilateral": _STORED,
        "perspectives": _STORED,
    }
}


class PerspectiveKind(StrEnum):
    PARTY_TOPIC = "party_topic"


class PerspectiveRepository:
    def __init__(self, client: Elasticsearch, index: str) -> None:
        self.client = client
        self.index = index

    def congresses(self) -> list[int]:
        """Congresses with stored perspectives, newest first."""
        try:
            response = self.client.search(
                index=self.index,
                size=0,
                query={"term": {"kind": PerspectiveKind.PARTY_TOPIC}},
                aggs={
                    "congresses": {
                        "terms": {"field": CONGRESS_FIELD, "size": CONGRESS_BUCKETS}
                    }
                },
            )
        except NotFoundError:
            return []
        buckets = response["aggregations"]["congresses"]["buckets"]
        return sorted((int(bucket["key"]) for bucket in buckets), reverse=True)

    def read(self, congress: int) -> tuple[list[TopicPerspectives], str | None]:
        """The newest build of one Congress's topics and its topic-model version."""
        try:
            response = self.client.search(
                index=self.index,
                size=SCAN_SIZE,
                query={
                    "bool": {
                        "filter": [
                            {"term": {"kind": PerspectiveKind.PARTY_TOPIC}},
                            {"term": {CONGRESS_FIELD: congress}},
                        ]
                    }
                },
                sort=[{BUILT_AT_FIELD: {"order": "desc"}}],
            )
        except NotFoundError:
            return [], None
        hits = response["hits"]["hits"]
        if not hits:
            return [], None
        newest = hits[0]["_source"][MODEL_VERSION_FIELD]
        topics = [
            TopicPerspectives.model_validate(hit["_source"])
            for hit in hits
            if hit["_source"][MODEL_VERSION_FIELD] == newest
        ]
        return topics, str(newest)

    def replace(
        self,
        congress: int,
        model_version: str,
        built_at: str,
        results: Sequence[TopicPerspectives],
    ) -> int:
        """Swaps one Congress's stored topics for a fresh build; returns documents written."""
        if not self.client.indices.exists(index=self.index):
            self.client.indices.create(index=self.index)
        self.client.indices.put_mapping(
            index=self.index, properties=PERSPECTIVE_MAPPINGS["properties"]
        )
        self.client.delete_by_query(
            index=self.index,
            query={
                "bool": {
                    "filter": [
                        {"term": {"kind": PerspectiveKind.PARTY_TOPIC}},
                        {"term": {CONGRESS_FIELD: congress}},
                    ]
                }
            },
            refresh=True,
            conflicts="proceed",
        )
        written, _ = bulk(
            self.client,
            self.actions(model_version, built_at, results),
            refresh=True,
        )
        return int(written)

    def actions(
        self, model_version: str, built_at: str, results: Sequence[TopicPerspectives]
    ) -> Iterator[JsonObject]:
        for result in results:
            yield {
                "_index": self.index,
                "_id": (
                    f"{PerspectiveKind.PARTY_TOPIC}:{model_version}:"
                    f"{result.congress}:{result.topic_id}"
                ),
                "kind": PerspectiveKind.PARTY_TOPIC,
                MODEL_VERSION_FIELD: model_version,
                BUILT_AT_FIELD: built_at,
                **result.model_dump(mode="json"),
            }

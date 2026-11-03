"""Publishes one validated, refreshable perspective snapshot per Congress."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Literal, Self

from elasticsearch import Elasticsearch, NotFoundError
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from cdm.config.topic_analysis import (
    PerspectiveField,
    PerspectiveKind,
    PerspectiveSchema,
    PerspectiveStoreConfig,
)
from cdm.perspectives.models import TopicPerspectives
from cdm.store.client import SearchCompletion


class PerspectivePublication(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal[PerspectiveKind.PUBLICATION] = PerspectiveKind.PUBLICATION
    congress: int = Field(gt=0)
    model_version: str = Field(min_length=1)
    built_at: AwareDatetime
    results: list[TopicPerspectives]

    @staticmethod
    def document_id(congress: int) -> str:
        return f"{PerspectiveKind.PUBLICATION}:{congress}"

    @model_validator(mode="after")
    def validate_scope(self) -> Self:
        if any(result.congress != self.congress for result in self.results):
            raise ValueError("Perspective results must belong to the snapshot Congress")
        if len({result.topic_id for result in self.results}) != len(self.results):
            raise ValueError("Perspective snapshot has duplicate topic IDs")
        return self


class PerspectiveRepository:
    def __init__(
        self,
        client: Elasticsearch,
        index: str,
        settings: PerspectiveStoreConfig | None = None,
    ) -> None:
        self.client = client
        self.index = index
        self._settings = settings or PerspectiveStoreConfig()

    def congresses(self) -> list[int]:
        """Congresses with stored perspectives, newest first."""
        try:
            response = self.client.search(
                index=self.index,
                size=0,
                allow_partial_search_results=False,
                query={"terms": {"kind": list(PerspectiveKind)}},
                aggs={
                    "congresses": {
                        "terms": {
                            "field": PerspectiveField.CONGRESS,
                            "size": self._settings.congress_buckets,
                        }
                    }
                },
            )
        except NotFoundError:
            return []
        SearchCompletion.model_validate(response.body).require_complete()
        buckets = response["aggregations"]["congresses"]["buckets"]
        return sorted((int(bucket["key"]) for bucket in buckets), reverse=True)

    def read(self, congress: int) -> tuple[list[TopicPerspectives], str | None]:
        """One coherent snapshot, falling back to untouched pre-snapshot records."""
        try:
            response = self.client.get(
                index=self.index, id=PerspectivePublication.document_id(congress)
            )
        except NotFoundError:
            return self._legacy_read(congress)
        publication = PerspectivePublication.model_validate(response["_source"])
        if publication.congress != congress:
            raise ValueError("Perspective snapshot identity does not match Congress")
        return publication.results, publication.model_version

    def _legacy_read(self, congress: int) -> tuple[list[TopicPerspectives], str | None]:
        try:
            response = self.client.search(
                index=self.index,
                size=self._settings.legacy_limit,
                allow_partial_search_results=False,
                query={
                    "bool": {
                        "filter": [
                            {"term": {"kind": PerspectiveKind.PARTY_TOPIC}},
                            {"term": {PerspectiveField.CONGRESS: congress}},
                        ]
                    }
                },
                sort=[{PerspectiveField.BUILT_AT: {"order": "desc"}}],
            )
        except NotFoundError:
            return [], None
        SearchCompletion.model_validate(response.body).require_complete()
        hits = response["hits"]["hits"]
        if not hits:
            return [], None
        newest = hits[0]["_source"][PerspectiveField.MODEL_VERSION]
        topics = [
            TopicPerspectives.model_validate(hit["_source"])
            for hit in hits
            if hit["_source"][PerspectiveField.MODEL_VERSION] == newest
        ]
        return topics, str(newest)

    def replace(
        self,
        congress: int,
        model_version: str,
        built_at: datetime,
        results: Sequence[TopicPerspectives],
    ) -> int:
        """Atomically refresh one Congress; return the number of published topics."""
        publication = PerspectivePublication(
            congress=congress,
            model_version=model_version,
            built_at=built_at,
            results=list(results),
        )
        properties = PerspectiveSchema.properties()
        if not self.client.indices.exists(index=self.index):
            self.client.indices.create(
                index=self.index, mappings={"properties": properties}
            )
        else:
            self.client.indices.put_mapping(index=self.index, properties=properties)
        self.client.index(
            index=self.index,
            id=PerspectivePublication.document_id(congress),
            document=publication.model_dump(mode="json"),
            refresh="wait_for",
        )
        return len(publication.results)

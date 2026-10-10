"""Versioned, append-only manual metasubject names kept in Elasticsearch."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from cdm.utils.metasubjects import MetasubjectOverrides

OVERRIDE_SCAN_SIZE = 10000


class OverrideField(StrEnum):
    METASUBJECT_ID = "metasubject_id"
    VERSION = "version"
    NAME = "name"
    CREATED_AT = "created_at"


class OverrideVersion(BaseModel):
    """One edit; a null name is a tombstone that removes the override."""

    metasubject_id: int
    version: int
    name: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MetasubjectOverrideStore:
    def __init__(self, client: Any, index: str) -> None:
        self.client = client
        self.index = index

    def ensure_index(self) -> None:
        if self.client.indices.exists(index=self.index):
            return
        self.client.indices.create(
            index=self.index,
            mappings={
                "properties": {
                    OverrideField.METASUBJECT_ID: {"type": "integer"},
                    OverrideField.VERSION: {"type": "integer"},
                    OverrideField.NAME: {"type": "keyword"},
                    OverrideField.CREATED_AT: {"type": "date"},
                }
            },
        )

    def history(self, metasubject_id: int | None = None) -> list[OverrideVersion]:
        """Every stored edit, oldest first, optionally for one metasubject."""
        if not self.client.indices.exists(index=self.index):
            return []
        query: dict[str, Any] = (
            {"term": {OverrideField.METASUBJECT_ID: metasubject_id}}
            if metasubject_id is not None
            else {"match_all": {}}
        )
        response = self.client.search(
            index=self.index, size=OVERRIDE_SCAN_SIZE, query=query
        )
        versions = [
            OverrideVersion.model_validate(hit["_source"])
            for hit in response["hits"]["hits"]
        ]
        return sorted(versions, key=lambda v: (v.metasubject_id, v.version))

    def current(self) -> MetasubjectOverrides:
        """The newest version of each metasubject's name, tombstones dropped."""
        latest: dict[int, OverrideVersion] = {}
        for version in self.history():
            latest[version.metasubject_id] = version
        return MetasubjectOverrides(
            names={i: v.name for i, v in latest.items() if v.name}
        )

    def _append(self, metasubject_id: int, name: str | None) -> OverrideVersion:
        self.ensure_index()
        past = self.history(metasubject_id)
        edit = OverrideVersion(
            metasubject_id=metasubject_id,
            version=past[-1].version + 1 if past else 1,
            name=name,
        )
        self.client.index(
            index=self.index,
            id=f"{edit.metasubject_id}:{edit.version}",
            document=edit.model_dump(mode="json"),
            op_type="create",
            refresh="wait_for",
        )
        return edit

    def set_name(self, metasubject_id: int, name: str) -> OverrideVersion:
        return self._append(metasubject_id, name.strip())

    def clear(self, metasubject_id: int) -> OverrideVersion:
        return self._append(metasubject_id, None)

"""Decides which listed bills need an API refresh by comparing with the index."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from elasticsearch import Elasticsearch
from elasticsearch.helpers import scan
from pydantic import BaseModel

from cdm.models.bills import BillMetadata
from cdm.utils.json_types import JsonObject

DATE_PREFIX_LENGTH = 10


class ItemFilter(Protocol):
    """Chooses which listed items are worth an item-detail fetch."""

    def needs_refresh(self, meta: BaseModel) -> bool: ...


class IndexedBillState(BaseModel):
    """What the index already knows about one bill."""

    update_date: str | None = None
    has_subject_data: bool = False
    hydrated: bool = False

    @classmethod
    def from_source(cls, source: JsonObject) -> IndexedBillState:
        subjects = source.get("subjects")
        legislative = (
            subjects.get("legislative_subjects") if isinstance(subjects, dict) else None
        )
        update_date = source.get("update_date")
        return cls(
            update_date=str(update_date) if update_date else None,
            has_subject_data=bool(legislative) or bool(source.get("policy_area")),
            hydrated=bool(source.get("hydrated_at")),
        )


class IndexedBillStateReader:
    """Loads the indexed state of every bill in one Congress."""

    SOURCE_FIELDS = (
        "update_date",
        "hydrated_at",
        "subjects.legislative_subjects",
        "policy_area",
    )

    def __init__(self, client: Elasticsearch, index: str) -> None:
        self._client = client
        self._index = index

    def read(self, congress: int) -> dict[str, IndexedBillState]:
        query = {
            "bool": {
                "filter": [
                    {"term": {"source_type": "bill"}},
                    {"term": {"congress": congress}},
                ]
            }
        }
        return {
            str(hit["_id"]): IndexedBillState.from_source(hit.get("_source") or {})
            for hit in scan(
                self._client,
                index=self._index,
                query={"query": query, "_source": list(self.SOURCE_FIELDS)},
            )
        }


class StaleBillFilter:
    """Keeps bills that are new, changed upstream, or never filled in."""

    def __init__(self, states: Mapping[str, IndexedBillState]) -> None:
        self._states = states

    @staticmethod
    def bill_key(meta: BillMetadata) -> str:
        return f"bill:{meta.congress}:{meta.type.lower()}:{meta.number}"

    def needs_refresh(self, meta: BaseModel) -> bool:
        if not isinstance(meta, BillMetadata):
            return True
        state = self._states.get(self.bill_key(meta))
        if state is None:
            return True
        if meta.update_date and (
            state.update_date is None
            or meta.update_date[:DATE_PREFIX_LENGTH]
            > state.update_date[:DATE_PREFIX_LENGTH]
        ):
            return True
        # Docs that never had an API fetch and carry no subject data are skeletons.
        return not state.hydrated and not state.has_subject_data

"""Shared helpers for specialized sync workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from elasticsearch import Elasticsearch
from elasticsearch.helpers import scan

from knowledgebase.indexing import index_records
from knowledgebase.setup import IndexSpec, KnowledgebaseSetup
from src.data_collection.specialized.state import get_state, upsert_state
from src.data_collection.utils import PaginatedFetchResult, gather_paginated_records, resolve_pagination


def ensure_index(client: Elasticsearch, index_name: str, mapping: dict[str, Any]) -> None:
    setup = KnowledgebaseSetup(client)
    setup.create_index(IndexSpec(name=index_name, mapping=mapping))


def existing_ids(client: Elasticsearch, index_name: str) -> set[str]:
    hits = scan(client, index=index_name, _source=False)
    return {str(hit.get("_id")) for hit in hits}


def index_missing_records(
    client: Elasticsearch,
    index_name: str,
    records: list[dict[str, Any]],
    id_builder: Callable[[dict[str, Any]], Any],
    *,
    chunk_size: int,
) -> tuple[int, list[dict[str, Any]]]:
    if not records:
        return 0, []
    indexed, errors = index_records(
        client,
        index_name,
        records,
        id_builder,
        chunk_size=chunk_size,
    )
    return indexed, errors


@dataclass(frozen=True)
class PaginatedSyncSpec:
    index_name: str
    endpoint: str
    mapping: dict[str, Any]
    data_key: str
    id_builder: Callable[[dict[str, Any]], Any]
    page_size: int = 250
    chunk_size: int = 200
    progress_desc: str = "Pages"
    progress_unit: str = "page"


def fetch_total(
    fetch_page: Callable[[int, int], dict],
    *,
    data_key: str,
) -> int:
    response = fetch_page(0, 1)
    meta = resolve_pagination(
        response,
        records_len=len(response.get(str(data_key), [])),
        offset=0,
        page_size=1,
    )
    return meta.total


def fetch_paginated(
    fetch_page: Callable[[int, int], dict],
    *,
    data_key: str,
    desc: str,
    unit: str,
    page_size: int,
    on_progress: Callable[[int, int, int, int], None] | None = None,
) -> PaginatedFetchResult:
    return gather_paginated_records(
        fetch_page,
        data_key=data_key,
        desc=desc,
        unit=unit,
        page_size=page_size,
        progress_mode="page",
        on_progress=on_progress,
    )


def sync_records(
    es_client: Elasticsearch,
    *,
    index_name: str,
    endpoint: str,
    mapping: dict[str, Any],
    records: list[dict[str, Any]],
    id_builder: Callable[[dict[str, Any]], Any],
    current_total: int,
    state_id: str | None = None,
    chunk_size: int = 200,
    compare_index_count: bool = True,
) -> dict[str, Any]:
    ensure_index(es_client, index_name, mapping)
    state_key = state_id or index_name
    es_count = int(es_client.count(index=index_name).get("count", 0))
    state = get_state(es_client, state_key)
    previous_total = int(state.get("total", 0))

    if compare_index_count:
        if current_total == es_count and current_total == previous_total:
            return {
                "indexed": 0,
                "missing": 0,
                "current_total": current_total,
                "previous_total": previous_total,
            }
    else:
        if current_total == previous_total:
            return {
                "indexed": 0,
                "missing": 0,
                "current_total": current_total,
                "previous_total": previous_total,
            }

    for record in records:
        id_builder(record)

    existing = existing_ids(es_client, index_name)
    missing_records = [r for r in records if str(r.get("id")) not in existing]

    indexed = 0
    errors: list[dict[str, Any]] = []
    if missing_records:
        indexed, errors = index_missing_records(
            es_client,
            index_name,
            missing_records,
            id_builder,
            chunk_size=chunk_size,
        )

    upsert_state(
        es_client,
        state_key,
        endpoint,
        index=index_name,
        total=current_total,
        indexed=int(es_client.count(index=index_name).get("count", 0)),
    )

    return {
        "indexed": indexed,
        "missing": len(missing_records),
        "current_total": current_total,
        "previous_total": previous_total,
        "errors": errors,
    }


def sync_paginated_index(
    es_client: Elasticsearch,
    *,
    fetch_page: Callable[[int, int], dict],
    spec: PaginatedSyncSpec,
    state_id: str | None = None,
    existing: set[str] | None = None,
    compare_index_count: bool = True,
) -> dict[str, Any]:
    ensure_index(es_client, spec.index_name, spec.mapping)
    state_key = state_id or spec.index_name

    current_total = fetch_total(fetch_page, data_key=spec.data_key)
    if current_total == 0:
        return {
            "indexed": 0,
            "missing": 0,
            "current_total": current_total,
            "previous_total": 0,
            "errors": [],
        }

    es_count = int(es_client.count(index=spec.index_name).get("count", 0))
    state = get_state(es_client, state_key)
    previous_total = int(state.get("total", 0))

    if compare_index_count:
        if current_total == es_count and current_total == previous_total:
            return {
                "indexed": 0,
                "missing": 0,
                "current_total": current_total,
                "previous_total": previous_total,
            }
    else:
        if current_total == previous_total:
            return {
                "indexed": 0,
                "missing": 0,
                "current_total": current_total,
                "previous_total": previous_total,
            }

    def _store_progress(
        last_offset: int,
        last_page: int,
        total_pages: int,
        effective_page_size: int,
    ) -> None:
        upsert_state(
            es_client,
            state_key,
            spec.endpoint,
            index=spec.index_name,
            total=current_total,
            indexed=es_count,
            offset=last_offset,
            page=last_page,
            page_size=effective_page_size,
            pages=total_pages or None,
            status="running",
        )

    result = fetch_paginated(
        fetch_page,
        data_key=spec.data_key,
        desc=spec.progress_desc,
        unit=spec.progress_unit,
        page_size=spec.page_size,
        on_progress=_store_progress,
    )
    if result.total:
        current_total = result.total

    for record in result.records:
        spec.id_builder(record)

    existing_ids_set = existing if existing is not None else existing_ids(
        es_client, spec.index_name
    )
    missing_records = [
        r for r in result.records if str(r.get("id")) not in existing_ids_set
    ]

    indexed = 0
    errors: list[dict[str, Any]] = []
    if missing_records:
        indexed, errors = index_missing_records(
            es_client,
            spec.index_name,
            missing_records,
            spec.id_builder,
            chunk_size=spec.chunk_size,
        )
        if indexed and existing is not None:
            existing.update(str(r.get("id")) for r in missing_records)

    upsert_state(
        es_client,
        state_key,
        spec.endpoint,
        index=spec.index_name,
        total=current_total,
        indexed=int(es_client.count(index=spec.index_name).get("count", 0)),
        offset=0,
        page=result.last_page,
        page_size=result.page_size,
        pages=result.total_pages or None,
        status="complete",
    )

    return {
        "indexed": indexed,
        "missing": len(missing_records),
        "current_total": current_total,
        "previous_total": previous_total,
        "errors": errors,
    }

"""Shared helpers for specialized sync workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from elasticsearch import Elasticsearch
from elasticsearch.helpers import scan

from knowledgebase.indexing import index_records
from knowledgebase.setup import IndexSpec, KnowledgebaseSetup
from src.data_collection.specialized.state import get_state, upsert_state
from src.data_collection.utils import (
    PaginatedFetchResult,
    gather_paginated_records,
    resolve_pagination,
)


def ensure_index(
    client: Elasticsearch, index_name: str, mapping: dict[str, Any]
) -> None:
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
    start_offset: int = 0,
) -> PaginatedFetchResult:
    return gather_paginated_records(
        fetch_page,
        data_key=data_key,
        desc=desc,
        unit=unit,
        page_size=page_size,
        progress_mode="page",
        on_progress=on_progress,
        start_offset=start_offset,
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
    state = get_state(es_client, state_key)
    resume_offset = int(state.get("offset") or 0)

    last_progress = {
        "offset": resume_offset,
        "page": int(state.get("page") or 0),
        "pages": int(state.get("pages") or 0),
        "page_size": int(state.get("page_size") or spec.page_size),
    }

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
        last_progress.update(
            {
                "offset": last_offset,
                "page": last_page,
                "pages": total_pages or last_progress.get("pages", 0),
                "page_size": effective_page_size,
            }
        )
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

    indexed = 0
    errors: list[dict[str, Any]] = []
    existing_ids_set = (
        existing if existing is not None else existing_ids(es_client, spec.index_name)
    )
    page_index = int(resume_offset / (spec.page_size or 1)) if spec.page_size else 0

    try:
        offset = resume_offset
        total_pages = 0
        effective_page_size = spec.page_size
        while True:
            response = fetch_page(offset, spec.page_size)
            records = response.get(str(spec.data_key), [])
            if not records:
                break

            meta = resolve_pagination(
                response,
                records_len=len(records),
                offset=offset,
                page_size=spec.page_size,
            )
            if meta.total:
                current_total = meta.total
            effective_page_size = meta.page_size or len(records) or spec.page_size
            if current_total and effective_page_size:
                total_pages = (
                    current_total + effective_page_size - 1
                ) // effective_page_size

            page_index += 1
            _store_progress(offset, page_index, total_pages, effective_page_size)

            for record in records:
                spec.id_builder(record)
            missing_records = [
                r for r in records if str(r.get("id")) not in existing_ids_set
            ]
            if missing_records:
                new_indexed, new_errors = index_missing_records(
                    es_client,
                    spec.index_name,
                    missing_records,
                    spec.id_builder,
                    chunk_size=spec.chunk_size,
                )
                indexed += new_indexed
                errors.extend(new_errors)
                if new_indexed:
                    existing_ids_set.update(str(r.get("id")) for r in missing_records)

            next_offset = meta.next_offset
            if next_offset == -1 or next_offset == offset:
                break
            offset = next_offset

        upsert_state(
            es_client,
            state_key,
            spec.endpoint,
            index=spec.index_name,
            total=current_total,
            indexed=int(es_client.count(index=spec.index_name).get("count", 0)),
            offset=0,
            page=page_index,
            page_size=effective_page_size,
            pages=total_pages or None,
            status="complete",
        )
    except Exception:
        upsert_state(
            es_client,
            state_key,
            spec.endpoint,
            index=spec.index_name,
            total=current_total,
            indexed=int(es_client.count(index=spec.index_name).get("count", 0)),
            offset=last_progress.get("offset", resume_offset),
            page=last_progress.get("page"),
            page_size=last_progress.get("page_size"),
            pages=last_progress.get("pages") or None,
            status="failed",
        )
        raise

    return {
        "indexed": indexed,
        "missing": None,
        "current_total": current_total,
        "previous_total": previous_total,
        "errors": errors,
    }

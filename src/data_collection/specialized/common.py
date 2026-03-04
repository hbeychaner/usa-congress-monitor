"""Shared helpers for specialized sync workflows."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from math import ceil
from typing import Any, Callable

from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_scan

from knowledgebase.indexing import index_records
from knowledgebase.setup import IndexSpec, KnowledgebaseSetup
from src.data_collection.specialized.state import get_state, upsert_state
from src.data_collection.utils import (
    PaginatedFetchResult,
    gather_paginated_records,
    resolve_pagination,
)
from src.utils.logger import get_logger
from tqdm import tqdm

logger = get_logger(__name__)


async def ensure_index(
    client: AsyncElasticsearch, index_name: str, mapping: dict[str, Any]
) -> None:
    setup = KnowledgebaseSetup(client)
    await setup.create_index(IndexSpec(name=index_name, mapping=mapping))


async def existing_ids(client: AsyncElasticsearch, index_name: str) -> set[str]:
    hits = async_scan(client, index=index_name, _source=False)
    results: set[str] = set()
    async for hit in hits:
        results.add(str(hit.get("_id")))
    return results


async def index_missing_records(
    client: AsyncElasticsearch,
    index_name: str,
    records: list[dict[str, Any]],
    id_builder: Callable[[dict[str, Any]], Any],
    *,
    chunk_size: int,
) -> tuple[int, list[dict[str, Any]]]:
    if not records:
        return 0, []
    indexed, errors = await index_records(
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
    queue_size: int = 100
    worker_count: int = 2


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


async def sync_records(
    es_client: AsyncElasticsearch,
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
    await ensure_index(es_client, index_name, mapping)
    state_key = state_id or index_name
    es_count = int((await es_client.count(index=index_name)).get("count", 0))
    state = await get_state(es_client, state_key)
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

    existing = await existing_ids(es_client, index_name)
    missing_records = [r for r in records if str(r.get("id")) not in existing]

    indexed = 0
    errors: list[dict[str, Any]] = []
    if missing_records:
        indexed, errors = await index_missing_records(
            es_client,
            index_name,
            missing_records,
            id_builder,
            chunk_size=chunk_size,
        )

    await upsert_state(
        es_client,
        state_key,
        endpoint,
        index=index_name,
        total=current_total,
        indexed=int((await es_client.count(index=index_name)).get("count", 0)),
    )

    return {
        "indexed": indexed,
        "missing": len(missing_records),
        "current_total": current_total,
        "previous_total": previous_total,
        "errors": errors,
    }


async def sync_paginated_index(
    es_client: AsyncElasticsearch,
    *,
    fetch_page: Callable[[int, int], dict],
    spec: PaginatedSyncSpec,
    state_id: str | None = None,
    existing: set[str] | None = None,
    compare_index_count: bool = True,
) -> dict[str, Any]:
    await ensure_index(es_client, spec.index_name, spec.mapping)
    state_key = state_id or spec.index_name
    state = await get_state(es_client, state_key)
    resume_offset = int(state.get("offset") or 0)

    last_progress = {
        "offset": resume_offset,
        "page": int(state.get("page") or 0),
        "pages": int(state.get("pages") or 0),
        "page_size": int(state.get("page_size") or spec.page_size),
    }

    async def _fetch_page(offset: int, page_size: int) -> dict:
        return await asyncio.to_thread(fetch_page, offset, page_size)

    async def _fetch_total() -> int:
        response = await _fetch_page(0, 1)
        meta = resolve_pagination(
            response,
            records_len=len(response.get(str(spec.data_key), [])),
            offset=0,
            page_size=1,
        )
        return meta.total

    current_total = await _fetch_total()
    if current_total == 0:
        return {
            "indexed": 0,
            "missing": 0,
            "current_total": current_total,
            "previous_total": 0,
            "errors": [],
        }

    es_count = int((await es_client.count(index=spec.index_name)).get("count", 0))
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

    indexed = 0
    errors: list[dict[str, Any]] = []
    if existing is not None:
        existing_ids_set = existing
    else:
        logger.info("Scanning existing ids for %s...", spec.index_name)
        existing_ids_set = await existing_ids(es_client, spec.index_name)
        logger.info(
            "Loaded %s existing ids for %s", len(existing_ids_set), spec.index_name
        )
    page_index = int(resume_offset / (spec.page_size or 1)) if spec.page_size else 0

    try:
        offset = resume_offset
        total_pages = 0
        effective_page_size = spec.page_size
        base_count = es_count

        logger.info(
            "Starting paginated sync for %s (resume offset=%s)",
            spec.index_name,
            resume_offset,
        )
        pbar = tqdm(desc=spec.progress_desc, unit=spec.progress_unit)
        if page_index:
            pbar.n = page_index
            pbar.refresh()

        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(
            maxsize=spec.queue_size
        )

        async def _store_progress(
            last_offset: int,
            last_page: int,
            total_pages_value: int,
            effective_size: int,
            status: str,
        ) -> None:
            last_progress.update(
                {
                    "offset": last_offset,
                    "page": last_page,
                    "pages": total_pages_value or last_progress.get("pages", 0),
                    "page_size": effective_size,
                }
            )
            await upsert_state(
                es_client,
                state_key,
                spec.endpoint,
                index=spec.index_name,
                total=current_total,
                indexed=base_count + indexed,
                offset=last_offset,
                page=last_page,
                page_size=effective_size,
                pages=total_pages_value or None,
                status=status,
            )

        async def worker() -> None:
            nonlocal indexed, errors
            while True:
                item = await queue.get()
                if item is None:
                    queue.task_done()
                    break
                records = item["records"]
                meta = item["meta"]
                for record in records:
                    spec.id_builder(record)
                missing_records = [
                    r for r in records if str(r.get("id")) not in existing_ids_set
                ]
                if missing_records:
                    new_indexed, new_errors = await index_missing_records(
                        es_client,
                        spec.index_name,
                        missing_records,
                        spec.id_builder,
                        chunk_size=spec.chunk_size,
                    )
                    indexed += new_indexed
                    errors.extend(new_errors)
                    if new_indexed:
                        existing_ids_set.update(
                            str(r.get("id")) for r in missing_records
                        )
                await _store_progress(
                    meta["offset"],
                    meta["page"],
                    meta["pages"],
                    meta["page_size"],
                    status="running",
                )
                pbar.update(1)
                queue.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(spec.worker_count)]

        while True:
            response = await _fetch_page(offset, spec.page_size)
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
                total_pages = ceil(current_total / effective_page_size)
                if pbar.total != total_pages:
                    pbar.total = total_pages
                    pbar.refresh()

            page_index += 1
            await queue.put(
                {
                    "records": records,
                    "meta": {
                        "offset": offset,
                        "page": page_index,
                        "page_size": effective_page_size,
                        "pages": total_pages,
                    },
                }
            )

            next_offset = meta.next_offset
            if next_offset == -1 or next_offset == offset:
                break
            offset = next_offset

        for _ in workers:
            await queue.put(None)
        await queue.join()
        await asyncio.gather(*workers)

        pbar.close()

        await _store_progress(
            0, page_index, total_pages, effective_page_size, "complete"
        )
    except Exception:
        await upsert_state(
            es_client,
            state_key,
            spec.endpoint,
            index=spec.index_name,
            total=current_total,
            indexed=int((await es_client.count(index=spec.index_name)).get("count", 0)),
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

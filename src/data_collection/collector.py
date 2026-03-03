"""Orchestrate list collection and record enrichment with retries and checkpoints.

This module provides helpers to:
- fetch list-level data from paginated endpoints,
- enrich list items by calling detail endpoints,
- persist progress to disk for resumable collection runs.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, MutableMapping, Optional

from tqdm import tqdm

from src.data_collection.utils import extract_offset, resolve_pagination_wait


ListFetcher = Callable[[int, int], Mapping[str, Any]]
DetailFetcher = Callable[[Mapping[str, Any]], Mapping[str, Any]]
IdGetter = Callable[[Mapping[str, Any]], str]


def retry_call(
    func: Callable[[], Mapping[str, Any]], retries: int = 3, backoff: float = 0.5
) -> Mapping[str, Any]:
    """Execute a callable with retry and exponential backoff."""
    for attempt in range(retries):
        try:
            return func()
        except Exception:
            if attempt >= retries - 1:
                raise
            time.sleep(backoff * (2**attempt))
    raise RuntimeError("Retry loop exhausted unexpectedly.")


def collect_paginated_list(
    fetch_page: ListFetcher,
    data_key: str,
    *,
    page_size: int = 250,
    wait: Optional[float] = None,
    checkpoint_path: Optional[Path] = None,
    results_path: Optional[Path] = None,
) -> list[Mapping[str, Any]]:
    """Collect list-level records from a paginated endpoint with checkpointing."""
    offset = 0
    records: list[Mapping[str, Any]] = []
    if checkpoint_path and checkpoint_path.exists():
        offset = json.loads(checkpoint_path.read_text(encoding="utf-8")).get(
            "offset", 0
        )
    if results_path and results_path.exists():
        records = json.loads(results_path.read_text(encoding="utf-8"))

    wait_val = resolve_pagination_wait(page_size, wait)
    pbar = tqdm(desc=f"Collecting {data_key}", unit="item")
    pbar.update(len(records))

    while True:
        response = fetch_page(offset, page_size)
        page_records = list(response.get(str(data_key), []))
        if not page_records:
            break
        records.extend(page_records)
        pbar.update(len(page_records))

        pagination = response.get("pagination", {})
        next_url = pagination.get("next") if isinstance(pagination, dict) else None
        if not next_url:
            break
        new_offset = extract_offset(next_url)
        if new_offset == offset:
            break
        offset = new_offset

        if results_path:
            results_path.write_text(json.dumps(records), encoding="utf-8")
        if checkpoint_path:
            checkpoint_path.write_text(json.dumps({"offset": offset}), encoding="utf-8")
        time.sleep(wait_val)

    pbar.close()
    return records


def enrich_records(
    items: Iterable[Mapping[str, Any]],
    *,
    detail_fetcher: DetailFetcher,
    id_getter: IdGetter,
    checkpoint_path: Optional[Path] = None,
    results_path: Optional[Path] = None,
    retries: int = 3,
    backoff: float = 0.5,
) -> list[Mapping[str, Any]]:
    """Enrich list items by fetching detail records with checkpointing."""
    enriched: MutableMapping[str, Mapping[str, Any]] = {}
    completed_ids: set[str] = set()

    if results_path and results_path.exists():
        enriched = {
            r["_id"]: r for r in json.loads(results_path.read_text(encoding="utf-8"))
        }
        completed_ids = set(enriched.keys())
    if checkpoint_path and checkpoint_path.exists():
        completed_ids.update(
            json.loads(checkpoint_path.read_text(encoding="utf-8")).get("completed", [])
        )

    items_list = list(items)
    pbar = tqdm(total=len(items_list), desc="Enriching records", unit="item")
    pbar.update(len(completed_ids))

    for item in items_list:
        record_id = id_getter(item)
        if record_id in completed_ids:
            continue

        detail = retry_call(
            lambda: detail_fetcher(item), retries=retries, backoff=backoff
        )
        enriched[record_id] = {"_id": record_id, **detail}
        completed_ids.add(record_id)
        pbar.update(1)

        if results_path:
            results_path.write_text(
                json.dumps(list(enriched.values())), encoding="utf-8"
            )
        if checkpoint_path:
            checkpoint_path.write_text(
                json.dumps({"completed": sorted(completed_ids)}), encoding="utf-8"
            )

    pbar.close()
    return list(enriched.values())


def collect_with_details(
    *,
    fetch_page: ListFetcher,
    data_key: str,
    detail_fetcher: DetailFetcher,
    id_getter: IdGetter,
    page_size: int = 250,
    wait: Optional[float] = None,
    list_checkpoint: Optional[Path] = None,
    list_results: Optional[Path] = None,
    detail_checkpoint: Optional[Path] = None,
    detail_results: Optional[Path] = None,
    retries: int = 3,
    backoff: float = 0.5,
) -> list[Mapping[str, Any]]:
    """Collect list items, then enrich them with detail data."""
    items = collect_paginated_list(
        fetch_page,
        data_key,
        page_size=page_size,
        wait=wait,
        checkpoint_path=list_checkpoint,
        results_path=list_results,
    )
    return enrich_records(
        items,
        detail_fetcher=detail_fetcher,
        id_getter=id_getter,
        checkpoint_path=detail_checkpoint,
        results_path=detail_results,
        retries=retries,
        backoff=backoff,
    )

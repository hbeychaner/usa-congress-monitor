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
from typing import Callable, Iterable, Mapping, MutableMapping, Optional, TypeAlias, Union

from tqdm import tqdm

from src.data_collection.utils import extract_offset, resolve_pagination_wait
from src.utils.logger import get_logger

logger = get_logger(__name__)


Json: TypeAlias = Union[str, int, float, bool, None, list["Json"], Mapping[str, "Json"]]


ListFetcher = Callable[[int, int], Mapping[str, Json]]
DetailFetcher = Callable[[Mapping[str, Json]], Mapping[str, Json]]
IdGetter = Callable[[Mapping[str, Json]], str]


def retry_call(
    func: Callable[[], Mapping[str, Json]], retries: int = 3, backoff: float = 0.5
) -> Mapping[str, Json]:
    """Call ``func`` with retries and exponential backoff.

    Args:
        func: zero-argument callable returning a JSON-like mapping.
        retries: number of attempts before giving up.
        backoff: base backoff seconds (exponential multiplier per attempt).

    Returns:
        The mapping returned by ``func`` on success.

    Raises:
        The last exception raised by ``func`` if all retries fail.
    """
    for attempt in range(retries):
        try:
            return func()
        except Exception:
            logger.warning("Retry attempt %s failed", attempt + 1)
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
) -> list[Mapping[str, Json]]:
    """Collect list-level records from a paginated endpoint with checkpointing.

    This helper repeatedly calls ``fetch_page(offset, page_size)`` until no more
    items are returned. Progress can be saved to ``results_path`` and
    ``checkpoint_path`` so collection can be resumed.
    """
    offset = 0
    records: list[Mapping[str, Json]] = []
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
        next_url = pagination.get("next") if isinstance(pagination, Mapping) else None
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
    items: Iterable[Mapping[str, Json]],
    *,
    detail_fetcher: DetailFetcher,
    id_getter: IdGetter,
    checkpoint_path: Optional[Path] = None,
    results_path: Optional[Path] = None,
    retries: int = 3,
    backoff: float = 0.5,
) -> list[Mapping[str, Json]]:
    """Fetch detail records for each item and checkpoint progress.

    Args:
        items: iterable of list-item mappings returned by list endpoints.
        detail_fetcher: callable that accepts a list-item mapping and returns the detail mapping.
        id_getter: callable that returns a stable string id for a given list-item mapping.
        checkpoint_path: optional Path to save completed ids for resuming.
        results_path: optional Path to save enriched records as they are produced.
        retries: retry attempts for individual detail fetches.
        backoff: base backoff seconds between retries.

    Returns:
        List of enriched detail mappings, each including an ``_id`` key.
    """
    enriched: MutableMapping[str, Mapping[str, Json]] = {}
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

        detail = retry_call(lambda: detail_fetcher(item), retries=retries, backoff=backoff)
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
) -> list[Mapping[str, Json]]:
    """Collect list items and enrich them with detail records.

    This convenience function first collects the paginated list, then
    fetches details for each list item with checkpointing.
    """
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

"""Shared utilities for endpoint pagination and date handling."""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Callable, Optional
from urllib.parse import parse_qs, urlparse

from requests.exceptions import ChunkedEncodingError
from tqdm import tqdm
from urllib3.exceptions import ProtocolError

RESULT_LIMIT = 100
RATE_LIMIT_CONSTANT = 5000 / 60 / 60  # 5000 requests per hour, divided into seconds


def checkpointed_paginate(
    endpoint_func,
    *args,
    from_date=None,
    to_date=None,
    max_retries=3,
    start_offset=0,
    **kwargs,
):
    """Paginate with checkpointing and batch persistence to disk.

    Filenames are derived from the endpoint function name and stored in the
    current working directory.
    """
    func_name = endpoint_func.__name__
    checkpoint_file = f"{func_name}_checkpoint.json"
    results_file = f"{func_name}_results.json"
    offset = start_offset
    try:
        with open(checkpoint_file, "r", encoding="utf-8") as f:
            offset = json.load(f)["offset"]
    except FileNotFoundError:
        pass
    try:
        with open(results_file, "r", encoding="utf-8") as f:
            all_results = json.load(f)
    except FileNotFoundError:
        all_results = []
    while offset != -1:
        for attempt in range(max_retries):
            try:
                call_kwargs = dict(kwargs)
                call_kwargs["offset"] = offset
                if from_date is not None:
                    call_kwargs["from_date"] = from_date
                if to_date is not None:
                    call_kwargs["to_date"] = to_date
                results, next_offset, count = endpoint_func(*args, **call_kwargs)
                break
            except (ChunkedEncodingError, ProtocolError) as exc:
                time.sleep(2)
        else:
            break
        all_results.extend(results)
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(all_results, f)
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump({"offset": next_offset}, f)
        offset = next_offset


def datetime_convert(date_str: str) -> str:
    """Convert a YYYY-MM-DD date to YYYY-MM-DDTHH:MM:SSZ."""
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    return date_obj.strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_offset(url: str) -> int:
    """Extract the pagination offset from a URL query string."""
    parsed_url = urlparse(url)
    offset = parse_qs(parsed_url.query).get("offset", [0])[0]
    return int(offset)


def determine_pagination_wait(start_time: float, offset: int) -> None:
    """Sleep as needed to respect the hourly request rate limit."""
    current_time = time.time()
    elapsed_time = current_time - start_time
    requests = max(RESULT_LIMIT, offset) / RESULT_LIMIT
    rate = elapsed_time / requests
    if rate < RATE_LIMIT_CONSTANT:
        wait_time = RATE_LIMIT_CONSTANT - rate
        time.sleep(wait_time)


def resolve_pagination_wait(page_size: int, wait: Optional[float] = None) -> float:
    """Resolve the delay between paginated requests."""
    if wait is not None:
        return wait
    return 0.5


def determine_simple_wait(start_time: float, api_call_count: int) -> None:
    """Sleep as needed to respect the hourly request rate limit."""
    current_time = time.time()
    elapsed_time = current_time - start_time
    rate = elapsed_time / api_call_count
    if rate < RATE_LIMIT_CONSTANT:
        wait_time = RATE_LIMIT_CONSTANT - rate
        time.sleep(wait_time)


def gather_paginated_metadata(
    fetch_page: Callable[[int, int], dict],
    data_key: str,
    desc: str,
    unit: str,
    page_size: int = 250,
    wait: Optional[float] = None,
) -> list:
    """Aggregate list results across paginated endpoint responses."""
    offset = 0
    all_records = []
    wait_val = resolve_pagination_wait(page_size, wait)
    pbar = tqdm(desc=desc, unit=unit)
    while True:
        response = fetch_page(offset, page_size)
        records = response.get(str(data_key), [])
        if not records:
            break
        all_records.extend(records)
        pbar.update(len(records))
        new_offset = extract_offset(response)
        if new_offset is None or new_offset == offset:
            break
        offset = new_offset
        time.sleep(wait_val)
    pbar.close()
    return all_records


def gather_single_page_metadata(fetch_page: Callable[[], dict], data_key: str) -> list:
    """Return the list of records from a single-page endpoint response."""
    response = fetch_page()
    return response.get(str(data_key), [])


def gather_data(
    endpoint_func: Callable[..., tuple[list, int, int]],
    *args,
    **kwargs,
) -> list:
    """Aggregate results from endpoints that return (results, next_offset, count)."""
    start = time.time()
    all_results = []
    offset = kwargs.pop("offset", 0)
    total_count = None
    pbar = None
    while offset != -1:
        results, next_offset, count = endpoint_func(*args, offset=offset, **kwargs)
        all_results.extend(results)
        if total_count is None:
            total_count = count
            if total_count:
                pbar = tqdm(total=total_count)
        if pbar:
            pbar.update(len(results))
        determine_pagination_wait(start, offset)
        offset = next_offset
    if pbar:
        pbar.close()
    return all_results

"""Shared utilities for endpoint pagination and date handling."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from dataclasses import dataclass
from math import ceil
from typing import Callable, Optional
from urllib.parse import parse_qs, urlparse

from pydantic import HttpUrl
from requests.exceptions import ChunkedEncodingError
from selenium import webdriver
from tqdm import tqdm
from urllib3.exceptions import ProtocolError

from src.utils.logger import get_logger

logger = get_logger(__name__)

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
                logger.warning("Paginated request failed: %s", exc)
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


def _extract_query_int(url: str, keys: tuple[str, ...]) -> Optional[int]:
    parsed_url = urlparse(url)
    params = parse_qs(parsed_url.query)
    for key in keys:
        if key in params and params[key]:
            try:
                return int(params[key][0])
            except (TypeError, ValueError):
                return None
    return None


def extract_offset_from_url(
    url: str,
    *,
    offset_param_names: tuple[str, ...] = ("offset", "start", "skip"),
    page_param_names: tuple[str, ...] = ("page", "pageNumber", "page_number"),
    page_size: Optional[int] = None,
) -> Optional[int]:
    """Extract an offset or page from a URL query string."""
    offset = _extract_query_int(url, offset_param_names)
    if offset is not None:
        return offset
    page = _extract_query_int(url, page_param_names)
    if page is not None and page_size:
        return max(0, (page - 1) * page_size)
    return None


@dataclass(frozen=True)
class PaginationMeta:
    next_offset: int
    total: int
    page_size: int


@dataclass(frozen=True)
class PaginatedFetchResult:
    records: list
    total: int
    last_page: int
    total_pages: int
    page_size: int


def resolve_pagination(
    response: dict,
    *,
    records_len: int,
    offset: int,
    page_size: int,
    offset_param_names: tuple[str, ...] = ("offset", "start", "skip"),
    page_param_names: tuple[str, ...] = ("page", "pageNumber", "page_number"),
) -> PaginationMeta:
    """Resolve pagination metadata from a response with varied conventions."""
    pagination = response.get("pagination")
    if isinstance(pagination, dict):
        total = int(pagination.get("total") or pagination.get("count") or 0)
        effective_page_size = int(
            pagination.get("limit")
            or pagination.get("pageSize")
            or pagination.get("pagesize")
            or page_size
            or records_len
            or 0
        )
        next_offset = -1
        next_url = pagination.get("next") or pagination.get("nextPage")
        if isinstance(next_url, str):
            extracted = extract_offset_from_url(
                next_url,
                offset_param_names=offset_param_names,
                page_param_names=page_param_names,
                page_size=effective_page_size or page_size,
            )
            if extracted is not None:
                next_offset = extracted
        else:
            offset_value = pagination.get("offset")
            if offset_value is not None:
                try:
                    next_offset = int(offset_value)
                except (TypeError, ValueError):
                    next_offset = -1
        return PaginationMeta(next_offset=next_offset, total=total, page_size=effective_page_size)

    results = response.get("Results")
    if isinstance(results, dict):
        total = int(results.get("TotalCount") or results.get("total") or 0)
        index_start = results.get("IndexStart")
        effective_page_size = page_size or records_len or 0
        if index_start is None:
            return PaginationMeta(next_offset=-1, total=total, page_size=effective_page_size)
        try:
            index_start_int = int(index_start)
        except (TypeError, ValueError):
            index_start_int = offset
        next_offset = index_start_int + records_len
        if total and next_offset >= total:
            next_offset = -1
        return PaginationMeta(next_offset=next_offset, total=total, page_size=effective_page_size)

    return PaginationMeta(next_offset=-1, total=0, page_size=page_size or records_len or 0)


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
    result = gather_paginated_records(
        fetch_page,
        data_key=data_key,
        desc=desc,
        unit=unit,
        page_size=page_size,
        wait=wait,
        progress_mode="record",
    )
    return result.records


def gather_paginated_records(
    fetch_page: Callable[[int, int], dict],
    *,
    data_key: str,
    desc: str,
    unit: str,
    page_size: int = 250,
    wait: Optional[float] = None,
    progress_mode: str = "record",
    on_progress: Optional[Callable[[int, int, int, int], None]] = None,
    offset_param_names: tuple[str, ...] = ("offset", "start", "skip"),
    page_param_names: tuple[str, ...] = ("page", "pageNumber", "page_number"),
    start_offset: int = 0,
) -> PaginatedFetchResult:
    """Aggregate list results across paginated endpoint responses."""
    offset = start_offset
    all_records: list = []
    wait_val = resolve_pagination_wait(page_size, wait)
    pbar = tqdm(desc=desc, unit=unit)
    total = 0
    total_pages = 0
    page_index = 0
    effective_page_size = page_size
    while True:
        response = fetch_page(offset, page_size)
        records = response.get(str(data_key), [])
        if not records:
            break
        all_records.extend(records)
        meta = resolve_pagination(
            response,
            records_len=len(records),
            offset=offset,
            page_size=page_size,
            offset_param_names=offset_param_names,
            page_param_names=page_param_names,
        )
        if total == 0 and meta.total:
            total = meta.total
            effective_page_size = meta.page_size or len(records) or page_size
            total_pages = ceil(total / effective_page_size) if effective_page_size else 0
            if progress_mode == "page" and total_pages:
                pbar.total = total_pages
                pbar.refresh()
        page_index += 1
        if progress_mode == "page":
            pbar.update(1)
            if total_pages:
                pbar.set_postfix_str(f"{page_index}/{total_pages}")
        else:
            pbar.update(len(records))
        if on_progress:
            on_progress(offset, page_index, total_pages, effective_page_size)
        if meta.next_offset == -1 or meta.next_offset == offset:
            break
        offset = meta.next_offset
        time.sleep(wait_val)
    pbar.close()
    return PaginatedFetchResult(
        records=all_records,
        total=total,
        last_page=page_index,
        total_pages=total_pages,
        page_size=effective_page_size,
    )


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


def download_pdf(lnk: HttpUrl) -> str:
    """Download a PDF from a link using Selenium.

    Returns the filename of the downloaded PDF.
    """
    options = webdriver.ChromeOptions()
    download_folder = os.path.join(os.getcwd(), "tmp")
    profile = {
        "plugins.plugins_list": [{"enabled": False, "name": "Chrome PDF Viewer"}],
        "download.default_directory": download_folder,
        "download.extensions_to_open": "",
        "plugins.always_open_pdf_externally": True,
    }
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_experimental_option("prefs", profile)
    driver = webdriver.Chrome(options=options)
    driver.get(str(lnk))

    filename = str(lnk).split("/")[-1]
    logger.info("Downloaded PDF: %s", filename)
    time.sleep(3)
    driver.close()
    return filename

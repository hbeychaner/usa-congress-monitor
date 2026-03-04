"""Endpoint helpers for Congress.gov bill resources."""

import time
from typing import Any

from tqdm import tqdm

from src.data_collection.client import CDGClient
from src.data_collection.endpoints.common import get_list
from src.data_collection.utils import (
    datetime_convert,
    determine_pagination_wait,
    extract_offset,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

RESULT_LIMIT = 100


def get_bills_metadata_by_date(
    client: CDGClient, from_date: str, to_date: str, offset: int = 0
) -> tuple[list[Any], int, int]:
    """Retrieve metadata for bills by date range."""
    from_date = datetime_convert(from_date)
    to_date = datetime_convert(to_date)
    params = {"limit": RESULT_LIMIT, "fromDateTime": from_date, "toDateTime": to_date}
    if offset > 0:
        params["offset"] = offset
    response = client.get("bill", params=params)
    if isinstance(response, dict):
        bills = list(response.get("bills", []))  # type: ignore
        pagination = response.get("pagination", {})
        if isinstance(pagination, dict) and "next" in pagination:
            offset = extract_offset(url=pagination["next"])
            count = int(pagination.get("count", 0))
            return (bills, offset, count)
        return (bills, -1, 0)
    return ([], -1, 0)


def gather_congress_bills(client: CDGClient, from_date: str, to_date: str) -> list:
    """Gather all bills for a given date range (paginated)."""
    from_date = datetime_convert(from_date)
    to_date = datetime_convert(to_date)
    start = time.time()
    bills = []
    offset = 0
    total_count = None
    pbar = None
    while offset != -1:
        result, offset, count = get_bills_metadata_by_date(
            client, from_date, to_date, offset
        )
        bills.extend(result)
        if total_count is None:
            total_count = count
            pbar = tqdm(total=total_count, desc="Retrieving bills")
        if pbar:
            pbar.update(len(result))
        determine_pagination_wait(start, offset)  # Prevent rate limiting
    if pbar:
        pbar.close()
    return bills


def get_bills_metadata(client: CDGClient, offset: int = 0, limit: int = 250):
    """Retrieve bills metadata (paginated)."""
    return get_list(client, "bill", offset=offset, limit=limit)

"""Endpoint helpers for Congressional Record resources."""

from src.data_collection.client import CDGClient
from src.data_collection.utils import gather_paginated_metadata
from src.models.data_types import CongressDataType
from src.utils.logger import get_logger

logger = get_logger(__name__)
from typing import Optional


def get_congressional_records(
    client: CDGClient,
    offset: int = 0,
    pageSize: int = 250,
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
):
    """
    Retrieve congressional records metadata (paginated).
    Args:
        client (CDGClient): The client object.
        offset (int): The offset for pagination.
        pageSize (int): Number of items per page.
    Returns:
        dict: Dictionary containing congressional record data.
    """
    params = {"offset": offset, "pageSize": pageSize}
    if year is not None:
        params["y"] = year
    if month is not None:
        params["m"] = month
    if day is not None:
        params["d"] = day
    return client.get("congressional-record", params=params)


def gather_congressional_records(
    client: CDGClient,
    pageSize: int = 250,
    wait: Optional[float] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
) -> list:
    """
    Gather all congressional records using pagination.
    Args:
        client (CDGClient): The client object.
        pageSize (int): Number of items per page.
        wait (float): Seconds to wait between requests (default: auto).
    Returns:
        list: A list of congressional record metadata.
    """

    def fetch_page(offset: int, page_size: int) -> dict:
        return get_congressional_records(
            client,
            offset=offset,
            pageSize=page_size,
            year=year,
            month=month,
            day=day,
        )

    response = fetch_page(0, pageSize)
    results = response.get("Results", {})
    return results.get("Issues", [])


def get_congressional_records_index(client: CDGClient, offset: int = 0):
    """Retrieve congressional record issues with offset-based pagination."""
    params = {"limit": 100}
    if offset > 0:
        params["offset"] = offset
    response = client.get("congressional-record", params=params)
    records = response.get("Results", {}).get("Issues", [])
    total_results = response.get("Results", {}).get("TotalCount")
    current_offset = response.get("Results", {}).get("IndexStart")
    new_offset = current_offset + len(response.get("Results", {}).get("Issues", []))
    if total_results is not None and new_offset >= total_results:
        new_offset = -1
    return (records, new_offset, total_results)

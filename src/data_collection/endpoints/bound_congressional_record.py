"""Endpoint helpers for bound Congressional Record resources."""

from src.data_collection.client import CDGClient
from src.data_collection.utils import gather_paginated_metadata
from src.data_collection.data_types import CongressDataType
from typing import Optional

def get_bound_congressional_records(client: CDGClient, offset: int = 0, pageSize: int = 250):
    """
    Retrieve bound congressional records metadata (paginated).
    Args:
        client (CDGClient): The client object.
        offset (int): The offset for pagination.
        pageSize (int): Number of items per page.
    Returns:
        dict: Dictionary containing bound congressional record data.
    """
    return client.get("bound-congressional-record", params={"offset": offset, "pageSize": pageSize})


def gather_bound_congressional_records(client: CDGClient, pageSize: int = 250, wait: Optional[float] = None) -> list:
    """
    Gather all bound congressional records using pagination.
    Args:
        client (CDGClient): The client object.
        pageSize (int): Number of items per page.
        wait (float): Seconds to wait between requests (default: auto).
    Returns:
        list: A list of bound congressional record metadata.
    """
    return gather_paginated_metadata(
        lambda offset, page_size: get_bound_congressional_records(
            client, offset=offset, pageSize=page_size
        ),
        data_key=CongressDataType.BOUND_CONGRESSIONAL_RECORD,
        desc="Bound Congressional Records",
        unit="record",
        page_size=pageSize,
        wait=wait,
    )


def get_bound_congressional_records_by_year(client: CDGClient, year: int):
    """Retrieve bound Congressional Records filtered by year."""
    return client.get(f"bound-congressional-record/{year}")


def get_bound_congressional_records_by_year_and_month(
    client: CDGClient, year: int, month: int
):
    """Retrieve bound Congressional Records filtered by year and month."""
    return client.get(f"bound-congressional-record/{year}/{month}")


def get_bound_congressional_records_by_year_month_and_day(
    client: CDGClient, year: int, month: int, day: int
):
    """Retrieve bound Congressional Records filtered by year, month, and day."""
    return client.get(f"bound-congressional-record/{year}/{month}/{day}")

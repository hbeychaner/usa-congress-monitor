"""Endpoint helpers for daily Congressional Record resources."""

from src.data_collection.client import CDGClient
from src.data_collection.utils import gather_paginated_metadata
from src.data_collection.data_types import CongressDataType
from typing import Optional

def get_daily_congressional_records(client: CDGClient, offset: int = 0, pageSize: int = 250):
    """
    Retrieve daily congressional records metadata (paginated).
    Args:
        client (CDGClient): The client object.
        offset (int): The offset for pagination.
        pageSize (int): Number of items per page.
    Returns:
        dict: Dictionary containing daily congressional record data.
    """
    return client.get("daily-congressional-record", params={"offset": offset, "pageSize": pageSize})


def gather_daily_congressional_records(client: CDGClient, pageSize: int = 250, wait: Optional[float] = None) -> list:
    """
    Gather all daily congressional records using pagination.
    Args:
        client (CDGClient): The client object.
        pageSize (int): Number of items per page.
        wait (float): Seconds to wait between requests (default: auto).
    Returns:
        list: A list of daily congressional record metadata.
    """
    return gather_paginated_metadata(
        lambda offset, page_size: get_daily_congressional_records(
            client, offset=offset, pageSize=page_size
        ),
        data_key=CongressDataType.DAILY_CONGRESSIONAL_RECORD,
        desc="Daily Congressional Records",
        unit="record",
        page_size=pageSize,
        wait=wait,
    )


def get_daily_congressional_records_by_volume(client: CDGClient, volume_number: int):
    """Retrieve daily Congressional Records filtered by volume number."""
    return client.get(f"daily-congressional-record/{volume_number}")


def get_daily_congressional_records_by_volume_and_issue(
    client: CDGClient, volume_number: int, issue_number: int
):
    """Retrieve daily Congressional Records filtered by volume and issue."""
    return client.get(f"daily-congressional-record/{volume_number}/{issue_number}")


def get_daily_congressional_record_articles(
    client: CDGClient, volume_number: int, issue_number: int
):
    """Retrieve daily Congressional Record articles for a volume and issue."""
    return client.get(
        f"daily-congressional-record/{volume_number}/{issue_number}/articles"
    )

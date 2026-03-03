"""Endpoint helpers for summary resources."""

from src.data_collection.client import CDGClient
from src.data_collection.utils import gather_paginated_metadata
from src.models.data_types import CongressDataType
from typing import Optional


def get_summaries(client: CDGClient, offset: int = 0, pageSize: int = 250):
    """
    Retrieve summaries metadata (paginated).
    Args:
        client (CDGClient): The client object.
        offset (int): The offset for pagination.
        pageSize (int): Number of items per page.
    Returns:
        dict: Dictionary containing summaries data.
    """
    return client.get("summaries", params={"offset": offset, "pageSize": pageSize})


def gather_summaries(
    client: CDGClient, pageSize: int = 250, wait: Optional[float] = None
) -> list:
    """
    Gather all summaries using pagination.
    Args:
        client (CDGClient): The client object.
        pageSize (int): Number of items per page.
        wait (float): Seconds to wait between requests (default: auto).
    Returns:
        list: A list of summaries metadata.
    """
    return gather_paginated_metadata(
        lambda offset, page_size: get_summaries(
            client, offset=offset, pageSize=page_size
        ),
        data_key=CongressDataType.SUMMARIES,
        desc="Summaries",
        unit="summary",
        page_size=pageSize,
        wait=wait,
    )

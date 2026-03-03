"""Endpoint helpers for House communication resources."""

from src.data_collection.client import CDGClient
from src.data_collection.utils import gather_paginated_metadata
from src.data_collection.data_types import CongressDataType
from typing import Optional

def get_house_communications(client: CDGClient, offset: int = 0, pageSize: int = 250):
    """
    Retrieve House communications metadata (paginated).
    Args:
        client (CDGClient): The client object.
        offset (int): The offset for pagination.
        pageSize (int): Number of items per page.
    Returns:
        dict: Dictionary containing House communication data.
    """
    return client.get("house-communication", params={"offset": offset, "pageSize": pageSize})


def gather_house_communications(client: CDGClient, pageSize: int = 250, wait: Optional[float] = None) -> list:
    """
    Gather all House communications using pagination.
    Args:
        client (CDGClient): The client object.
        pageSize (int): Number of items per page.
        wait (float): Seconds to wait between requests (default: auto).
    Returns:
        list: A list of House communication metadata.
    """
    return gather_paginated_metadata(
            lambda offset, page_size: get_house_communications(
                client, offset=offset, pageSize=page_size
            ),
            data_key=CongressDataType.HOUSE_COMMUNICATIONS,
            desc="House Communications",
            unit="communication",
            page_size=pageSize,
            wait=wait,
        )


def get_house_communications_by_congress(client: CDGClient, congress: int):
    """Retrieve House communications filtered by Congress."""
    return client.get(f"house-communication/{congress}")


def get_house_communications_by_congress_and_type(
    client: CDGClient, congress: int, communication_type: str
):
    """Retrieve House communications filtered by Congress and type."""
    return client.get(f"house-communication/{congress}/{communication_type}")


def get_house_communication_details(
    client: CDGClient, congress: int, communication_type: str, communication_number: int
):
    """Retrieve detailed information for a House communication."""
    return client.get(
        f"house-communication/{congress}/{communication_type}/{communication_number}"
    )

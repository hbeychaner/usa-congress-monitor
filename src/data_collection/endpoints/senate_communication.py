"""Endpoint helpers for Senate communication resources."""

from src.data_collection.client import CDGClient
from src.data_collection.utils import gather_paginated_metadata
from src.models.data_types import CongressDataType
from src.utils.logger import get_logger

logger = get_logger(__name__)
from typing import Optional


def get_senate_communications(client: CDGClient, offset: int = 0, pageSize: int = 250):
    """
    Retrieve Senate communications metadata (paginated).
    Args:
        client (CDGClient): The client object.
        offset (int): The offset for pagination.
        pageSize (int): Number of items per page.
    Returns:
        dict: Dictionary containing Senate communication data.
    """
    return client.get(
        "senate-communication", params={"offset": offset, "pageSize": pageSize}
    )


def gather_senate_communications(
    client: CDGClient, pageSize: int = 250, wait: Optional[float] = None
) -> list:
    """
    Gather all Senate communications using pagination.
    Args:
        client (CDGClient): The client object.
        pageSize (int): Number of items per page.
        wait (float): Seconds to wait between requests (default: auto).
    Returns:
        list: A list of Senate communication metadata.
    """
    return gather_paginated_metadata(
        lambda offset, page_size: get_senate_communications(
            client, offset=offset, pageSize=page_size
        ),
        data_key=CongressDataType.SENATE_COMMUNICATIONS,
        desc="Senate Communications",
        unit="communication",
        page_size=pageSize,
        wait=wait,
    )


def get_senate_communications_by_congress(client: CDGClient, congress: int):
    """Retrieve Senate communications filtered by Congress."""
    return client.get(f"senate-communication/{congress}")


def get_senate_communications_by_congress_and_type(
    client: CDGClient, congress: int, communication_type: str
):
    """Retrieve Senate communications filtered by Congress and type."""
    return client.get(f"senate-communication/{congress}/{communication_type}")


def get_senate_communication_details(
    client: CDGClient, congress: int, communication_type: str, communication_number: int
):
    """Retrieve detailed information for a Senate communication."""
    return client.get(
        f"senate-communication/{congress}/{communication_type}/{communication_number}"
    )

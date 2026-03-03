"""Endpoint helpers for hearing resources."""

from src.data_collection.client import CDGClient
from src.data_collection.utils import gather_paginated_metadata
from src.data_collection.data_types import CongressDataType
from typing import Optional

def get_hearings(client: CDGClient, offset: int = 0, pageSize: int = 250):
    """
    Retrieve hearings metadata (paginated).
    Args:
        client (CDGClient): The client object.
        offset (int): The offset for pagination.
        pageSize (int): Number of items per page.
    Returns:
        dict: Dictionary containing hearing data.
    """
    return client.get("hearing", params={"offset": offset, "pageSize": pageSize})


def gather_hearings(client: CDGClient, pageSize: int = 250, wait: Optional[float] = None) -> list:
    """
    Gather all hearings using pagination.
    Args:
        client (CDGClient): The client object.
        pageSize (int): Number of items per page.
        wait (float): Seconds to wait between requests (default: auto).
    Returns:
        list: A list of hearing metadata.
    """
    return gather_paginated_metadata(
        lambda offset, page_size: get_hearings(client, offset=offset, pageSize=page_size),
        data_key=CongressDataType.HEARINGS,
        desc="Hearings",
        unit="hearing",
        page_size=pageSize,
        wait=wait,
    )

def get_hearings_by_congress(client: CDGClient, congress: int):
    """Retrieve hearings filtered by Congress."""
    return client.get(f"hearing/{congress}")

def get_hearings_by_congress_and_chamber(
    client: CDGClient, congress: int, chamber: str
):
    """Retrieve hearings filtered by Congress and chamber."""
    return client.get(f"hearing/{congress}/{chamber}")

def get_hearing_details(
    client: CDGClient, congress: int, chamber: str, jacket_number: str
):
    """Retrieve detailed information for a hearing."""
    return client.get(f"hearing/{congress}/{chamber}/{jacket_number}")

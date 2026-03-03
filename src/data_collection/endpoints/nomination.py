"""Endpoint helpers for nomination resources."""

from src.data_collection.client import CDGClient
from src.data_collection.utils import gather_paginated_metadata
from src.models.data_types import CongressDataType
from typing import Optional


def get_nominations(client: CDGClient, offset: int = 0, pageSize: int = 250):
    """
    Retrieve nominations metadata (paginated).
    Args:
        client (CDGClient): The client object.
        offset (int): The offset for pagination.
        pageSize (int): Number of items per page.
    Returns:
        dict: Dictionary containing nomination data.
    """
    return client.get("nomination", params={"offset": offset, "pageSize": pageSize})


def gather_nominations(
    client: CDGClient, pageSize: int = 250, wait: Optional[float] = None
) -> list:
    """
    Gather all nominations using pagination.
    Args:
        client (CDGClient): The client object.
        pageSize (int): Number of items per page.
        wait (float): Seconds to wait between requests (default: auto).
    Returns:
        list: A list of nomination metadata.
    """
    return gather_paginated_metadata(
        lambda offset, page_size: get_nominations(
            client, offset=offset, pageSize=page_size
        ),
        data_key=CongressDataType.NOMINATIONS,
        desc="Nominations",
        unit="nomination",
        page_size=pageSize,
        wait=wait,
    )


def get_nominations_by_congress(client: CDGClient, congress: int):
    """Retrieve nominations filtered by Congress."""
    return client.get(f"nomination/{congress}")


def get_nomination_details(client: CDGClient, congress: int, nomination_number: int):
    """Retrieve detailed information for a nomination."""
    return client.get(f"nomination/{congress}/{nomination_number}")


def get_nominees_for_nomination(
    client: CDGClient, congress: int, nomination_number: int, ordinal: int
):
    """Retrieve nominees for a position within a nomination."""
    return client.get(f"nomination/{congress}/{nomination_number}/{ordinal}")


def get_nomination_actions(client: CDGClient, congress: int, nomination_number: int):
    """Retrieve actions for a nomination."""
    return client.get(f"nomination/{congress}/{nomination_number}/actions")


def get_nomination_committees(client: CDGClient, congress: int, nomination_number: int):
    """Retrieve committees associated with a nomination."""
    return client.get(f"nomination/{congress}/{nomination_number}/committees")


def get_nomination_hearings(client: CDGClient, congress: int, nomination_number: int):
    """Retrieve printed hearings associated with a nomination."""
    return client.get(f"nomination/{congress}/{nomination_number}/hearings")

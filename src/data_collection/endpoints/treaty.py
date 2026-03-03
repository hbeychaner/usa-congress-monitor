"""Endpoint helpers for treaty resources."""

from src.data_collection.client import CDGClient
from src.data_collection.utils import gather_paginated_metadata
from src.models.data_types import CongressDataType
from src.utils.logger import get_logger

logger = get_logger(__name__)
from typing import Optional


def get_treaties(client: CDGClient, offset: int = 0, pageSize: int = 250):
    """
    Retrieve treaties metadata (paginated).
    Args:
        client (CDGClient): The client object.
        offset (int): The offset for pagination.
        pageSize (int): Number of items per page.
    Returns:
        dict: Dictionary containing treaty data.
    """
    return client.get("treaty", params={"offset": offset, "pageSize": pageSize})


def gather_treaties(
    client: CDGClient, pageSize: int = 250, wait: Optional[float] = None
) -> list:
    """
    Gather all treaties using pagination.
    Args:
        client (CDGClient): The client object.
        pageSize (int): Number of items per page.
        wait (float): Seconds to wait between requests (default: auto).
    Returns:
        list: A list of treaty metadata.
    """
    return gather_paginated_metadata(
        lambda offset, page_size: get_treaties(
            client, offset=offset, pageSize=page_size
        ),
        data_key=CongressDataType.TREATIES,
        desc="Treaties",
        unit="treaty",
        page_size=pageSize,
        wait=wait,
    )


def get_treaties_by_congress(client: CDGClient, congress: int):
    """Retrieve treaties filtered by Congress."""
    return client.get(f"treaty/{congress}")


def get_treaty_details(client: CDGClient, congress: int, treaty_number: int):
    """Retrieve detailed information for a treaty."""
    return client.get(f"treaty/{congress}/{treaty_number}")


def get_partitioned_treaty_details(
    client: CDGClient, congress: int, treaty_number: int, treaty_suffix: str
):
    """Retrieve detailed information for a partitioned treaty."""
    return client.get(f"treaty/{congress}/{treaty_number}/{treaty_suffix}")


def get_treaty_actions(client: CDGClient, congress: int, treaty_number: int):
    """Retrieve actions for a treaty."""
    return client.get(f"treaty/{congress}/{treaty_number}/actions")


def get_partitioned_treaty_actions(
    client: CDGClient, congress: int, treaty_number: int, treaty_suffix: str
):
    """Retrieve actions for a partitioned treaty."""
    return client.get(f"treaty/{congress}/{treaty_number}/{treaty_suffix}/actions")


def get_treaty_committees(client: CDGClient, congress: int, treaty_number: int):
    """Retrieve committees associated with a treaty."""
    return client.get(f"treaty/{congress}/{treaty_number}/committees")

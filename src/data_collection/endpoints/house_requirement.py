"""Endpoint helpers for House requirement resources."""

from src.data_collection.client import CDGClient
from src.data_collection.utils import gather_paginated_metadata
from src.models.data_types import CongressDataType
from src.utils.logger import get_logger

logger = get_logger(__name__)
from typing import Optional


def get_house_requirements(client: CDGClient, offset: int = 0, pageSize: int = 250):
    """
    Retrieve House requirements metadata (paginated).
    Args:
        client (CDGClient): The client object.
        offset (int): The offset for pagination.
        pageSize (int): Number of items per page.
    Returns:
        dict: Dictionary containing House requirement data.
    """
    return client.get(
        "house-requirement", params={"offset": offset, "pageSize": pageSize}
    )


def gather_house_requirements(
    client: CDGClient, pageSize: int = 250, wait: Optional[float] = None
) -> list:
    """
    Gather all House requirements using pagination.
    Args:
        client (CDGClient): The client object.
        pageSize (int): Number of items per page.
        wait (float): Seconds to wait between requests (default: auto).
    Returns:
        list: A list of House requirement metadata.
    """
    return gather_paginated_metadata(
        lambda offset, page_size: get_house_requirements(
            client, offset=offset, pageSize=page_size
        ),
        data_key=CongressDataType.HOUSE_REQUIREMENTS,
        desc="House Requirements",
        unit="requirement",
        page_size=pageSize,
        wait=wait,
    )


def get_house_requirement_details(client: CDGClient, requirement_number: int):
    """Retrieve detailed information for a House requirement."""
    return client.get(f"house-requirement/{requirement_number}")


def get_matching_communications_for_house_requirement(
    client: CDGClient, requirement_number: int
):
    """Retrieve communications matching a House requirement."""
    return client.get(f"house-requirement/{requirement_number}/matching-communications")

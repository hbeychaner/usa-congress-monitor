"""Endpoint helpers for House roll call vote resources."""

from src.data_collection.client import CDGClient
from src.data_collection.utils import gather_paginated_metadata
from src.models.data_types import CongressDataType
from typing import Optional


def get_house_roll_call_votes(client: CDGClient, offset: int = 0, pageSize: int = 250):
    """
    Retrieve House roll call votes metadata (paginated).
    Args:
        client (CDGClient): The client object.
        offset (int): The offset for pagination.
        pageSize (int): Number of items per page.
    Returns:
        dict: Dictionary containing House roll call vote data.
    """
    return client.get("house-vote", params={"offset": offset, "pageSize": pageSize})


def gather_house_roll_call_votes(
    client: CDGClient, pageSize: int = 250, wait: Optional[float] = None
) -> list:
    """
    Gather all House roll call votes using pagination.
    Args:
        client (CDGClient): The client object.
        pageSize (int): Number of items per page.
        wait (float): Seconds to wait between requests (default: auto).
    Returns:
        list: A list of House roll call vote metadata.
    """
    return gather_paginated_metadata(
        lambda offset, page_size: get_house_roll_call_votes(
            client, offset=offset, pageSize=page_size
        ),
        data_key=CongressDataType.HOUSE_ROLL_CALL_VOTES,
        desc="House Roll Call Votes",
        unit="vote",
        page_size=pageSize,
        wait=wait,
    )

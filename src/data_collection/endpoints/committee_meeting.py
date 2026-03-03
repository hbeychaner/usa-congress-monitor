
"""Endpoint helpers for committee meeting resources."""

from src.data_collection.client import CDGClient
from src.data_collection.utils import gather_paginated_metadata
from src.data_collection.data_types import CongressDataType
from typing import Optional

def get_committee_meetings(client: CDGClient, offset: int = 0, pageSize: int = 250):
    """
    Retrieve committee meetings metadata (paginated).
    Args:
        client (CDGClient): The client object.
        offset (int): The offset for pagination.
        pageSize (int): Number of items per page.
    Returns:
        dict: Dictionary containing committee meeting data.
    """
    return client.get("committee-meeting", params={"offset": offset, "pageSize": pageSize})


def gather_committee_meetings(client: CDGClient, pageSize: int = 250, wait: Optional[float] = None) -> list:
    """
    Gather all committee meetings using pagination.
    Args:
        client (CDGClient): The client object.
        pageSize (int): Number of items per page.
        wait (float): Seconds to wait between requests (default: auto).
    Returns:
        list: A list of committee meeting metadata.
    """
    return gather_paginated_metadata(
        lambda offset, page_size: get_committee_meetings(
            client, offset=offset, pageSize=page_size
        ),
        data_key=CongressDataType.COMMITTEE_MEETINGS,
        desc="Committee Meetings",
        unit="meeting",
        page_size=pageSize,
        wait=wait,
    )


def get_committee_meetings_by_congress(client: CDGClient, congress: int):
    """Retrieve committee meetings filtered by Congress."""
    return client.get(f"committee-meeting/{congress}")


def get_committee_meetings_by_congress_and_chamber(
    client: CDGClient, congress: int, chamber: str
):
    """Retrieve committee meetings filtered by Congress and chamber."""
    return client.get(f"committee-meeting/{congress}/{chamber}")


def get_committee_meeting_details(
    client: CDGClient, congress: int, chamber: str, event_id: str
):
    """Retrieve detailed information for a committee meeting."""
    return client.get(f"committee-meeting/{congress}/{chamber}/{event_id}")

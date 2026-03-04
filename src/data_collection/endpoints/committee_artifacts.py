"""Endpoint helpers for committee meetings, reports, and prints."""

from src.data_collection.client import CDGClient
from src.data_collection.endpoints.common import gather_paginated, gather_single_page, get_list
from src.models.data_types import CongressDataType
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_committee_meetings(client: CDGClient, offset: int = 0, limit: int = 250):
    """Retrieve committee meetings metadata (paginated)."""
    return get_list(client, "committee-meeting", offset=offset, limit=limit)


def gather_committee_meetings(
    client: CDGClient, limit: int = 250, wait: float | None = None
) -> list:
    """Gather all committee meetings using pagination."""
    return gather_paginated(
        client,
        "committee-meeting",
        data_key=CongressDataType.COMMITTEE_MEETINGS,
        desc="Committee Meetings",
        unit="meeting",
        limit=limit,
        wait=wait,
    )


def get_committee_reports(client: CDGClient, offset: int = 0, limit: int = 250):
    """Retrieve committee reports metadata (paginated)."""
    return get_list(client, "committee-report", offset=offset, limit=limit)


def gather_committee_reports(
    client: CDGClient, limit: int = 250, wait: float | None = None
) -> list:
    """Gather all committee reports using pagination."""
    return gather_paginated(
        client,
        "committee-report",
        data_key=CongressDataType.REPORTS,
        desc="Committee Reports",
        unit="report",
        limit=limit,
        wait=wait,
    )


def get_committee_prints(client: CDGClient, offset: int = 0, limit: int = 250):
    """Retrieve committee prints metadata (paginated)."""
    return get_list(client, "committee-print", offset=offset, limit=limit)


def gather_committee_prints(client: CDGClient) -> list:
    """Gather all committee prints. (No pagination supported)"""
    return gather_single_page(
        client,
        "committee-print",
        data_key=CongressDataType.COMMITTEE_PRINTS,
    )


def get_committee_prints_by_congress(client: CDGClient, congress: int):
    """Retrieve committee prints filtered by Congress."""
    return client.get(f"committee-print/{congress}")


def get_committee_prints_by_congress_and_chamber(
    client: CDGClient, congress: int, chamber: str
):
    """Retrieve committee prints filtered by Congress and chamber."""
    return client.get(f"committee-print/{congress}/{chamber}")


def get_committee_print_details(
    client: CDGClient, congress: int, chamber: str, jacket_number: str
):
    """Retrieve detailed information for a specific committee print."""
    return client.get(f"committee-print/{congress}/{chamber}/{jacket_number}")


def get_committee_print_text(
    client: CDGClient, congress: int, chamber: str, jacket_number: str
):
    """Retrieve the list of texts for a committee print."""
    return client.get(f"committee-print/{congress}/{chamber}/{jacket_number}/text")

"""Endpoint helpers for hearing resources."""

from src.data_collection.client import CDGClient
from src.data_collection.endpoints.common import gather_paginated, get_list
from src.models.data_types import CongressDataType
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_hearings(client: CDGClient, offset: int = 0, limit: int = 250):
    """Retrieve hearings metadata (paginated)."""
    return get_list(client, "hearing", offset=offset, limit=limit)


def gather_hearings(client: CDGClient, limit: int = 250, wait: float | None = None) -> list:
    """Gather all hearings using pagination."""
    return gather_paginated(
        client,
        "hearing",
        data_key=CongressDataType.HEARINGS,
        desc="Hearings",
        unit="hearing",
        limit=limit,
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

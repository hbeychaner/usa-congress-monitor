"""Endpoint helpers for nomination resources."""

from src.data_collection.client import CDGClient
from src.data_collection.endpoints.common import gather_paginated, get_list
from src.models.data_types import CongressDataType
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_nominations(client: CDGClient, offset: int = 0, limit: int = 250):
    """Retrieve nominations metadata (paginated)."""
    return get_list(client, "nomination", offset=offset, limit=limit)


def gather_nominations(
    client: CDGClient, limit: int = 250, wait: float | None = None
) -> list:
    """Gather all nominations using pagination."""
    return gather_paginated(
        client,
        "nomination",
        data_key=CongressDataType.NOMINATIONS,
        desc="Nominations",
        unit="nomination",
        limit=limit,
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

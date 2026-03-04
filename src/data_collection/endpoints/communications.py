"""Endpoint helpers for House/Senate communications."""

from src.data_collection.client import CDGClient
from src.data_collection.endpoints.common import gather_paginated, get_list
from src.models.data_types import CongressDataType
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_house_communications(client: CDGClient, offset: int = 0, limit: int = 250):
    """Retrieve House communications metadata (paginated)."""
    return get_list(client, "house-communication", offset=offset, limit=limit)


def gather_house_communications(
    client: CDGClient, limit: int = 250, wait: float | None = None
) -> list:
    """Gather all House communications using pagination."""
    return gather_paginated(
        client,
        "house-communication",
        data_key=CongressDataType.HOUSE_COMMUNICATIONS,
        desc="House Communications",
        unit="communication",
        limit=limit,
        wait=wait,
    )


def get_house_communications_by_congress(client: CDGClient, congress: int):
    """Retrieve House communications filtered by Congress."""
    return client.get(f"house-communication/{congress}")


def get_house_communications_by_congress_and_type(
    client: CDGClient, congress: int, communication_type: str
):
    """Retrieve House communications filtered by Congress and type."""
    return client.get(f"house-communication/{congress}/{communication_type}")


def get_house_communication_details(
    client: CDGClient, congress: int, communication_type: str, communication_number: int
):
    """Retrieve detailed information for a House communication."""
    return client.get(
        f"house-communication/{congress}/{communication_type}/{communication_number}"
    )


def get_senate_communications(
    client: CDGClient, offset: int = 0, limit: int = 250
):
    """Retrieve Senate communications metadata (paginated)."""
    return get_list(client, "senate-communication", offset=offset, limit=limit)


def gather_senate_communications(
    client: CDGClient, limit: int = 250, wait: float | None = None
) -> list:
    """Gather all Senate communications using pagination."""
    return gather_paginated(
        client,
        "senate-communication",
        data_key=CongressDataType.SENATE_COMMUNICATIONS,
        desc="Senate Communications",
        unit="communication",
        limit=limit,
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

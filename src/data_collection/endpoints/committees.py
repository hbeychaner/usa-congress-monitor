"""Endpoint helpers for committee resources."""

from src.data_collection.client import CDGClient
from src.data_collection.endpoints.common import gather_single_page, get_list
from src.models.data_types import CongressDataType
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_committees(client: CDGClient, offset: int = 0, limit: int = 250):
    """Retrieve committees metadata (paginated)."""
    return get_list(client, "committee", offset=offset, limit=limit)


def gather_committees(client: CDGClient) -> list:
    """Gather all congressional committees. (No pagination supported)"""
    return gather_single_page(
        client,
        "committee",
        data_key=CongressDataType.COMMITTEES,
    )


def get_committees_by_chamber(client: CDGClient, chamber: str):
    """Retrieve committees filtered by chamber."""
    return client.get(f"committee/{chamber}")


def get_committees_by_congress(client: CDGClient, congress: int):
    """Retrieve committees filtered by Congress."""
    return client.get(f"committee/{congress}")


def get_committees_by_congress_and_chamber(
    client: CDGClient, congress: int, chamber: str
):
    """Retrieve committees filtered by Congress and chamber."""
    return client.get(f"committee/{congress}/{chamber}")


def get_committee_by_chamber_and_code(
    client: CDGClient, chamber: str, committee_code: str
):
    """Retrieve details for a specific committee by chamber and code."""
    return client.get(f"committee/{chamber}/{committee_code}")


def get_committee_bills(client: CDGClient, chamber: str, committee_code: str):
    """Retrieve legislation associated with a specific committee."""
    return client.get(f"committee/{chamber}/{committee_code}/bills")


def get_committee_reports_by_chamber_and_code(
    client: CDGClient, chamber: str, committee_code: str
):
    """Retrieve committee reports associated with a specific committee."""
    return client.get(f"committee/{chamber}/{committee_code}/reports")


def get_committee_nominations(client: CDGClient, chamber: str, committee_code: str):
    """Retrieve nominations associated with a specific committee."""
    return client.get(f"committee/{chamber}/{committee_code}/nominations")


def get_committee_house_communications(
    client: CDGClient, chamber: str, committee_code: str
):
    """Retrieve House communications associated with a specific committee."""
    return client.get(f"committee/{chamber}/{committee_code}/house-communication")


def get_committee_senate_communications(
    client: CDGClient, chamber: str, committee_code: str
):
    """Retrieve Senate communications associated with a specific committee."""
    return client.get(f"committee/{chamber}/{committee_code}/senate-communication")

"""Endpoint helpers for committee print resources."""

from src.data_collection.client import CDGClient
from src.data_collection.utils import gather_single_page_metadata
from src.models.data_types import CongressDataType


def get_committee_prints(client: CDGClient):
    """
    Retrieve a list of committee prints.
    Args:
        client (CDGClient): The client object.
    Returns:
        dict: Dictionary containing committee print data.
    """
    return client.get("committee-print")


def gather_committee_prints(client: CDGClient) -> list:
    """
    Gather all committee prints. (No pagination supported)
    Args:
        client (CDGClient): The client object.
    Returns:
        list: A list of committee print metadata.
    """
    return gather_single_page_metadata(
        lambda: get_committee_prints(client),
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

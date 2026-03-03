"""Endpoint helpers for committee resources."""

from src.data_collection.client import CDGClient
from src.data_collection.utils import gather_single_page_metadata
from src.data_collection.data_types import CongressDataType

def get_committees(client: CDGClient, offset: int = 0, pageSize: int = 250):
    """
    Retrieve committees metadata (paginated).

    Args:
        client (CDGClient): The client object.
        offset (int): The offset for pagination.
        pageSize (int): Number of items per page.

    Returns:
        dict: Dictionary containing committees data.
    """
    return client.get("committee", params={"offset": offset, "pageSize": pageSize})


def gather_committees(client: CDGClient) -> list:
    """
    Gather all congressional committees. (No pagination supported)

    Args:
        client (CDGClient): The client object.

    Returns:
        list: A list of committee metadata.
    """
    return gather_single_page_metadata(
        lambda: get_committees(client),
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

"""Endpoint helpers for committee report resources."""

from src.data_collection.client import CDGClient
from src.data_collection.utils import gather_single_page_metadata
from src.data_collection.data_types import CongressDataType


def get_committee_reports(client: CDGClient, offset: int = 0, pageSize: int = 250):
    """
    Retrieve committee reports metadata (paginated).

    Args:
        client (CDGClient): The client object.
        offset (int): The offset for pagination.
        pageSize (int): Number of items per page.

    Returns:
        dict: Dictionary containing committee reports data.
    """
    return client.get("committee-report", params={"offset": offset, "pageSize": pageSize})


def gather_committee_reports(client: CDGClient) -> list:
    """
    Gather all committee reports. (No pagination supported)

    Args:
        client (CDGClient): The client object.

    Returns:
        list: A list of committee report metadata.
    """
    return gather_single_page_metadata(
        lambda: get_committee_reports(client),
        data_key=CongressDataType.REPORTS,
    )


def get_committee_reports_by_congress(client: CDGClient, congress: int):
    """Retrieve committee reports filtered by Congress."""
    return client.get(f"committee-report/{congress}")


def get_committee_reports_by_congress_and_type(
    client: CDGClient, congress: int, report_type: str
):
    """Retrieve committee reports filtered by Congress and report type."""
    return client.get(f"committee-report/{congress}/{report_type}")


def get_committee_report_details(
    client: CDGClient, congress: int, report_type: str, report_number: int
):
    """Retrieve detailed information for a specific committee report."""
    return client.get(f"committee-report/{congress}/{report_type}/{report_number}")


def get_committee_report_text(
    client: CDGClient, congress: int, report_type: str, report_number: int
):
    """Retrieve the list of texts for a committee report."""
    return client.get(
        f"committee-report/{congress}/{report_type}/{report_number}/text"
    )

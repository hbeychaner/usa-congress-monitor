"""Endpoint helpers for CRS report resources."""

from src.data_collection.client import CDGClient
from src.data_collection.utils import gather_paginated_metadata
from src.models.data_types import CongressDataType
from src.utils.logger import get_logger

logger = get_logger(__name__)
from typing import Optional


def get_crs_reports(client: CDGClient, offset: int = 0, pageSize: int = 250):
    """
    Retrieve CRS reports metadata (paginated).
    Args:
        client (CDGClient): The client object.
        offset (int): The offset for pagination.
        pageSize (int): Number of items per page.
    Returns:
        dict: Dictionary containing CRS report data.
    """
    return client.get("crsreport", params={"offset": offset, "pageSize": pageSize})


def gather_crs_reports(
    client: CDGClient, pageSize: int = 250, wait: Optional[float] = None
) -> list:
    """
    Gather all CRS reports using pagination.
    Args:
        client (CDGClient): The client object.
        pageSize (int): Number of items per page.
        wait (float): Seconds to wait between requests (default: auto).
    Returns:
        list: A list of CRS report metadata.
    """
    return gather_paginated_metadata(
        lambda offset, page_size: get_crs_reports(
            client, offset=offset, pageSize=page_size
        ),
        data_key=CongressDataType.CRS_REPORTS,
        desc="CRS Reports",
        unit="report",
        page_size=pageSize,
        wait=wait,
    )


def get_crs_report_details(client: CDGClient, report_number: str):
    """Retrieve detailed information for a CRS report."""
    return client.get(f"crsreport/{report_number}")

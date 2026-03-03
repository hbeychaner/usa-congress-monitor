"""Endpoint helpers for Congress.gov amendment resources."""

from typing import Any

from src.data_collection.client import CDGClient
from src.data_collection.utils import datetime_convert, extract_offset

RESULT_LIMIT = 100


def get_amendments_metadata(
    client: CDGClient,
    from_date: str,
    to_date: str,
    offset: int = 0,
    limit: int = RESULT_LIMIT,
) -> tuple[list[Any], int, int]:
    """
    Retrieve metadata for amendments.
    Args:
        client (CDGClient): The client object.
        from_date (str): The start date for the search in the format "YYYY-MM-DDTHH:MM:SSZ".
        to_date (str): The end date for the search in the format "YYYY-MM-DDTHH:MM:SSZ".
        offset (int): The offset for the request.
        limit (int): The number of results to return.
    Returns:
        tuple: (list of amendment metadata, next offset, total count)
    """
    from_date = datetime_convert(from_date)
    to_date = datetime_convert(to_date)
    params = {"limit": limit, "fromDateTime": from_date, "toDateTime": to_date}
    if offset > 0:
        params["offset"] = offset
    response = client.get("amendment", params=params)
    if isinstance(response, dict):
        amendments = list(response.get("amendments", []))  # type: ignore
        pagination = response.get("pagination", {})
        if isinstance(pagination, dict) and "next" in pagination:
            offset = extract_offset(pagination["next"])
            count = int(pagination.get("count", 0))
            return (amendments, offset, count)
        return (amendments, -1, 0)
    else:
        return ([], -1, 0)


def get_amendments_metadata_paginated(
    client: CDGClient, offset: int = 0, pageSize: int = 250
):
    """
    Retrieve amendments metadata (paginated).
    Args:
        client (CDGClient): The client object.
        offset (int): The offset for pagination.
        pageSize (int): Number of items per page.
    Returns:
        dict: Dictionary containing amendments data.
    """
    return client.get("amendment", params={"offset": offset, "pageSize": pageSize})

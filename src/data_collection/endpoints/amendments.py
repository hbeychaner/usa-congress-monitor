"""Endpoint helpers for Congress.gov amendment resources."""

from typing import Any

from src.data_collection.client import CDGClient
from src.data_collection.endpoints.common import get_list
from src.data_collection.utils import datetime_convert, extract_offset
from src.utils.logger import get_logger

logger = get_logger(__name__)

RESULT_LIMIT = 100


def get_amendments_metadata(
    client: CDGClient,
    from_date: str,
    to_date: str,
    offset: int = 0,
    limit: int = RESULT_LIMIT,
) -> tuple[list[Any], int, int]:
    """Retrieve metadata for amendments by date range."""
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
    return ([], -1, 0)


def get_amendments_metadata_paginated(
    client: CDGClient,
    offset: int = 0,
    limit: int = 250,
):
    """Retrieve amendments metadata (paginated)."""
    return get_list(client, "amendment", offset=offset, limit=limit)

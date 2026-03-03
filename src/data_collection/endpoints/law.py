"""Endpoint helpers for law resources."""

from src.data_collection.client import CDGClient
from src.data_collection.utils import (
    extract_offset,
    gather_paginated_metadata,
    determine_pagination_wait,
)
from src.models.data_types import CongressDataType
from src.utils.logger import get_logger

logger = get_logger(__name__)
from typing import Any
from tqdm import tqdm
import time

# You may want to import these from a shared config/constants module
RESULT_LIMIT = 100


def get_laws_metadata(
    client: CDGClient, congress: int, offset: int = 0
) -> tuple[list[Any], int, int]:
    """
    Retrieve metadata for laws.

    Args:
        client (CDGClient): The client object.
        congress (int): The congress number.
        offset (int): The offset for the request.

    Returns:
        tuple: (list of law metadata, next offset, total count)
    """
    params = {
        "offset": offset,
        "pageSize": RESULT_LIMIT,
    }
    response = client.get(f"law/{congress}", params=params)
    if isinstance(response, dict):
        laws = list(response.get("bills", []))  # type: ignore
        pagination = response.get("pagination", {})
        if isinstance(pagination, dict) and "next" in pagination:
            offset = extract_offset(pagination["next"])
            count = int(pagination.get("count", 0))
            return (laws, offset, count)
        return (laws, -1, 0)
    else:
        return ([], -1, 0)


def gather_laws(client: CDGClient, congress: int) -> list:
    """
    Gather all laws for a given congress.

    Args:
        client (CDGClient): The client object.
        congress (int): The congress number.

    Returns:
        list: A list of law metadata.
    """
    start = time.time()
    laws = []
    offset = 0
    total_count = None
    pbar = None
    while offset != -1:
        result, offset, count = get_laws_metadata(client, congress, offset)
        laws.extend(result)
        if total_count is None:
            total_count = count
            pbar = tqdm(total=total_count, desc="Retrieving laws")
        if pbar:
            pbar.update(len(result))
        # You may want to import determine_pagination_wait from a shared utils module
        determine_pagination_wait(start, offset)  # Prevent rate limiting
    if pbar:
        pbar.close()
    return laws


def get_laws(client: CDGClient, congress: int, offset: int = 0, pageSize: int = 250):
    """
    Retrieve laws metadata (paginated).
    Args:
        client (CDGClient): The client object.
        congress (int): The congress number.
        offset (int): The offset for pagination.
        pageSize (int): Number of items per page.
    Returns:
        dict: Dictionary containing law data.
    """
    return client.get(
        f"law/{congress}", params={"offset": offset, "pageSize": pageSize}
    )


def gather_laws_paginated(
    client: CDGClient, congress: int, pageSize: int = 250, wait: float | None = None
) -> list:
    """
    Gather all laws using pagination.
    Args:
        client (CDGClient): The client object.
        congress (int): The congress number.
        pageSize (int): Number of items per page.
        wait (float): Seconds to wait between requests (default: auto).
    Returns:
        list: A list of law metadata.
    """
    return gather_paginated_metadata(
        lambda offset, page_size: get_laws(
            client, congress=congress, offset=offset, pageSize=page_size
        ),
        data_key=CongressDataType.LAWS,
        desc="Laws",
        unit="law",
        page_size=pageSize,
        wait=wait,
    )

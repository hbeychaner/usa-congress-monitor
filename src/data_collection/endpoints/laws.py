"""Endpoint helpers for law resources."""

import time
from typing import Any

from tqdm import tqdm

from src.data_collection.client import CDGClient
from src.data_collection.endpoints.common import gather_paginated, get_list
from src.data_collection.utils import determine_pagination_wait, extract_offset
from src.models.data_types import CongressDataType
from src.utils.logger import get_logger

logger = get_logger(__name__)

RESULT_LIMIT = 100


def get_laws_metadata(
    client: CDGClient, congress: int, offset: int = 0
) -> tuple[list[Any], int, int]:
    """Retrieve metadata for laws."""
    params = {
        "offset": offset,
        "limit": RESULT_LIMIT,
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
    return ([], -1, 0)


def gather_laws(client: CDGClient, congress: int) -> list:
    """Gather all laws for a given congress."""
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
        determine_pagination_wait(start, offset)  # Prevent rate limiting
    if pbar:
        pbar.close()
    return laws


def get_laws(
    client: CDGClient,
    congress: int,
    offset: int = 0,
    limit: int = 250,
):
    """Retrieve laws metadata (paginated)."""
    return get_list(client, f"law/{congress}", offset=offset, limit=limit)


def gather_laws_paginated(
    client: CDGClient, congress: int, limit: int = 250, wait: float | None = None
) -> list:
    """Gather all laws using pagination."""
    return gather_paginated(
        client,
        f"law/{congress}",
        data_key=CongressDataType.LAWS,
        desc="Laws",
        unit="law",
        limit=limit,
        wait=wait,
    )

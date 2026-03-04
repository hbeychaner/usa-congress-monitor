"""Shared helpers for Congress.gov endpoint modules."""

from __future__ import annotations

from typing import Any, Callable

from src.data_collection.client import CDGClient
from src.data_collection.utils import gather_paginated_metadata, gather_single_page_metadata
from src.models.data_types import CongressDataType


def get_list(
    client: CDGClient,
    endpoint: str,
    *,
    offset: int = 0,
    limit: int = 250,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fetch a paginated list endpoint with standard offset/limit parameters."""
    final_params: dict[str, Any] = {"offset": offset, "limit": limit}
    if params:
        final_params.update(params)
    return client.get(endpoint, params=final_params)


def gather_paginated(
    client: CDGClient,
    endpoint: str,
    *,
    data_key: CongressDataType,
    desc: str,
    unit: str,
    limit: int = 250,
    wait: float | None = None,
    params: dict[str, Any] | None = None,
) -> list:
    """Gather all records from a paginated list endpoint."""
    return gather_paginated_metadata(
        lambda offset, page_size: get_list(
            client, endpoint, offset=offset, limit=page_size, params=params
        ),
        data_key=data_key,
        desc=desc,
        unit=unit,
        page_size=limit,
        wait=wait,
    )


def gather_single_page(
    client: CDGClient,
    endpoint: str,
    *,
    data_key: CongressDataType,
    params: dict[str, Any] | None = None,
) -> list:
    """Gather records from a single-page endpoint."""
    return gather_single_page_metadata(
        lambda: client.get(endpoint, params=params),
        data_key=data_key,
    )

"""Endpoint helpers for Congressional Record resources."""

from __future__ import annotations

from src.data_collection.client import CDGClient
from src.data_collection.endpoints.common import gather_paginated, get_list
from src.models.data_types import CongressDataType
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_bound_congressional_records(
    client: CDGClient, offset: int = 0, limit: int = 250
):
    """Retrieve bound congressional records metadata (paginated)."""
    return get_list(client, "bound-congressional-record", offset=offset, limit=limit)


def enumerate_daily_congressional_record_volumes(
    client: CDGClient, congress_num: int
) -> list:
    """Enumerate unique volume numbers for daily congressional records for a given congress."""
    # Fetch all daily congressional records for the congress
    records = gather_daily_congressional_records(client)
    volumes = set()
    for record in records:
        volume = record.get("volumeNumber")
        if volume is not None:
            volumes.add(volume)
    return sorted(volumes)


def gather_bound_congressional_records(
    client: CDGClient, limit: int = 250, wait: float | None = None
) -> list:
    """Gather all bound congressional records using pagination."""
    return gather_paginated(
        client,
        "bound-congressional-record",
        data_key=CongressDataType.BOUND_CONGRESSIONAL_RECORD,
        desc="Bound Congressional Records",
        unit="record",
        limit=limit,
        wait=wait,
    )


def get_bound_congressional_records_by_year(client: CDGClient, year: int):
    """Retrieve bound Congressional Records filtered by year."""
    return client.get(f"bound-congressional-record/{year}")


def get_bound_congressional_records_by_year_and_month(
    client: CDGClient, year: int, month: int
):
    """Retrieve bound Congressional Records filtered by year and month."""
    return client.get(f"bound-congressional-record/{year}/{month}")


def get_bound_congressional_records_by_year_month_and_day(
    client: CDGClient, year: int, month: int, day: int
):
    """Retrieve bound Congressional Records filtered by year, month, and day."""
    return client.get(f"bound-congressional-record/{year}/{month}/{day}")


def get_daily_congressional_records(
    client: CDGClient, offset: int = 0, limit: int = 250
):
    """Retrieve daily congressional records metadata (paginated)."""
    return get_list(client, "daily-congressional-record", offset=offset, limit=limit)


def gather_daily_congressional_records(
    client: CDGClient, limit: int = 250, wait: float | None = None
) -> list:
    """Gather all daily congressional records using pagination."""
    return gather_paginated(
        client,
        "daily-congressional-record",
        data_key=CongressDataType.DAILY_CONGRESSIONAL_RECORD,
        desc="Daily Congressional Records",
        unit="record",
        limit=limit,
        wait=wait,
    )


def get_daily_congressional_records_by_volume(client: CDGClient, volume_number: int):
    """Retrieve daily Congressional Records filtered by volume number."""
    return client.get(f"daily-congressional-record/{volume_number}")


def get_daily_congressional_records_by_volume_and_issue(
    client: CDGClient, volume_number: int, issue_number: int
):
    """Retrieve daily Congressional Records filtered by volume and issue."""
    return client.get(f"daily-congressional-record/{volume_number}/{issue_number}")


def get_daily_congressional_record_articles(
    client: CDGClient, volume_number: int, issue_number: int
):
    """Retrieve daily Congressional Record articles for a volume and issue."""
    return client.get(
        f"daily-congressional-record/{volume_number}/{issue_number}/articles"
    )


def get_congressional_records(
    client: CDGClient,
    offset: int = 0,
    limit: int = 250,
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
):
    """Retrieve congressional records metadata (paginated)."""
    params = {"offset": offset, "limit": limit}
    if year is not None:
        params["y"] = year
    if month is not None:
        params["m"] = month
    if day is not None:
        params["d"] = day
    return client.get("congressional-record", params=params)


def gather_congressional_records(
    client: CDGClient,
    limit: int = 250,
    wait: float | None = None,
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
) -> list:
    """Gather congressional record issues (single page for date filters)."""

    def fetch_page(offset: int, page_size: int) -> dict:
        return get_congressional_records(
            client,
            offset=offset,
            limit=page_size,
            year=year,
            month=month,
            day=day,
        )

    response = fetch_page(0, limit)
    results = response.get("Results", {})
    return results.get("Issues", [])


def get_congressional_records_index(client: CDGClient, offset: int = 0):
    """Retrieve congressional record issues with offset-based pagination."""
    params = {"limit": 100}
    if offset > 0:
        params["offset"] = offset
    response = client.get("congressional-record", params=params)
    records = response.get("Results", {}).get("Issues", [])
    total_results = response.get("Results", {}).get("TotalCount")
    current_offset = response.get("Results", {}).get("IndexStart")
    new_offset = current_offset + len(response.get("Results", {}).get("Issues", []))
    if total_results is not None and new_offset >= total_results:
        new_offset = -1
    return (records, new_offset, total_results)

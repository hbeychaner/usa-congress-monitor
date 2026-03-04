"""Endpoint helpers for CRS reports, summaries, treaties, requirements, votes."""

from src.data_collection.client import CDGClient
from src.data_collection.endpoints.common import gather_paginated, get_list
from src.models.data_types import CongressDataType
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_crs_reports(client: CDGClient, offset: int = 0, limit: int = 250):
    """Retrieve CRS reports metadata (paginated)."""
    return get_list(client, "crsreport", offset=offset, limit=limit)


def gather_crs_reports(
    client: CDGClient, limit: int = 250, wait: float | None = None
) -> list:
    """Gather all CRS reports using pagination."""
    return gather_paginated(
        client,
        "crsreport",
        data_key=CongressDataType.CRS_REPORTS,
        desc="CRS Reports",
        unit="report",
        limit=limit,
        wait=wait,
    )


def get_crs_report_details(client: CDGClient, report_number: str):
    """Retrieve detailed information for a CRS report."""
    return client.get(f"crsreport/{report_number}")


def get_summaries(client: CDGClient, offset: int = 0, limit: int = 250):
    """Retrieve summaries metadata (paginated)."""
    return get_list(client, "summaries", offset=offset, limit=limit)


def gather_summaries(
    client: CDGClient, limit: int = 250, wait: float | None = None
) -> list:
    """Gather all summaries using pagination."""
    return gather_paginated(
        client,
        "summaries",
        data_key=CongressDataType.SUMMARIES,
        desc="Summaries",
        unit="summary",
        limit=limit,
        wait=wait,
    )


def get_treaties(client: CDGClient, offset: int = 0, limit: int = 250):
    """Retrieve treaties metadata (paginated)."""
    return get_list(client, "treaty", offset=offset, limit=limit)


def gather_treaties(
    client: CDGClient, limit: int = 250, wait: float | None = None
) -> list:
    """Gather all treaties using pagination."""
    return gather_paginated(
        client,
        "treaty",
        data_key=CongressDataType.TREATIES,
        desc="Treaties",
        unit="treaty",
        limit=limit,
        wait=wait,
    )


def get_treaties_by_congress(client: CDGClient, congress: int):
    """Retrieve treaties filtered by Congress."""
    return client.get(f"treaty/{congress}")


def get_treaty_details(client: CDGClient, congress: int, treaty_number: int):
    """Retrieve detailed information for a treaty."""
    return client.get(f"treaty/{congress}/{treaty_number}")


def get_partitioned_treaty_details(
    client: CDGClient, congress: int, treaty_number: int, treaty_suffix: str
):
    """Retrieve detailed information for a partitioned treaty."""
    return client.get(f"treaty/{congress}/{treaty_number}/{treaty_suffix}")


def get_treaty_actions(client: CDGClient, congress: int, treaty_number: int):
    """Retrieve actions for a treaty."""
    return client.get(f"treaty/{congress}/{treaty_number}/actions")


def get_partitioned_treaty_actions(
    client: CDGClient, congress: int, treaty_number: int, treaty_suffix: str
):
    """Retrieve actions for a partitioned treaty."""
    return client.get(f"treaty/{congress}/{treaty_number}/{treaty_suffix}/actions")


def get_treaty_committees(client: CDGClient, congress: int, treaty_number: int):
    """Retrieve committees associated with a treaty."""
    return client.get(f"treaty/{congress}/{treaty_number}/committees")


def get_house_requirements(client: CDGClient, offset: int = 0, limit: int = 250):
    """Retrieve House requirements metadata (paginated)."""
    return get_list(client, "house-requirement", offset=offset, limit=limit)


def gather_house_requirements(
    client: CDGClient, limit: int = 250, wait: float | None = None
) -> list:
    """Gather all House requirements using pagination."""
    return gather_paginated(
        client,
        "house-requirement",
        data_key=CongressDataType.HOUSE_REQUIREMENTS,
        desc="House Requirements",
        unit="requirement",
        limit=limit,
        wait=wait,
    )


def get_house_roll_call_votes(
    client: CDGClient, offset: int = 0, limit: int = 250
):
    """Retrieve House roll call votes metadata (paginated)."""
    return get_list(client, "house-vote", offset=offset, limit=limit)


def gather_house_roll_call_votes(
    client: CDGClient, limit: int = 250, wait: float | None = None
) -> list:
    """Gather all House roll call votes using pagination."""
    return gather_paginated(
        client,
        "house-vote",
        data_key=CongressDataType.HOUSE_ROLL_CALL_VOTES,
        desc="House Roll Call Votes",
        unit="vote",
        limit=limit,
        wait=wait,
    )

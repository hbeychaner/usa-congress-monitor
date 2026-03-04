"""Endpoint helpers for member resources."""

from src.data_collection.client import CDGClient
from src.data_collection.endpoints.common import gather_single_page, get_list
from src.models.data_types import CongressDataType
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_members_list(client: CDGClient, offset: int = 0, limit: int = 250):
    """Retrieve members metadata (paginated)."""
    return get_list(client, "member", offset=offset, limit=limit)


def gather_members(client: CDGClient) -> list:
    """Gather all congressional members. (No pagination supported)"""
    return gather_single_page(
        client,
        "member",
        data_key=CongressDataType.MEMBERS,
    )


def get_member_details(client: CDGClient, bioguide_id: str):
    """Retrieve detailed information for a specified congressional member."""
    return client.get(f"member/{bioguide_id}")


def get_member_sponsored_legislation(client: CDGClient, bioguide_id: str):
    """Retrieve legislation sponsored by a specified congressional member."""
    return client.get(f"member/{bioguide_id}/sponsored-legislation")


def get_member_cosponsored_legislation(client: CDGClient, bioguide_id: str):
    """Retrieve legislation cosponsored by a specified congressional member."""
    return client.get(f"member/{bioguide_id}/cosponsored-legislation")


def get_members_by_congress(client: CDGClient, congress: int):
    """Retrieve members filtered by Congress."""
    return client.get(f"member/congress/{congress}")


def get_members_by_state(client: CDGClient, state_code: str):
    """Retrieve members filtered by state."""
    return client.get(f"member/{state_code}")


def get_members_by_state_and_district(
    client: CDGClient, state_code: str, district: int
):
    """Retrieve members filtered by state and district."""
    return client.get(f"member/{state_code}/{district}")


def get_members_by_congress_state_and_district(
    client: CDGClient, congress: int, state_code: str, district: int
):
    """Retrieve members filtered by Congress, state, and district."""
    return client.get(f"member/congress/{congress}/{state_code}/{district}")

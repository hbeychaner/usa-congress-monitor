"""Endpoint helpers for Congress metadata resources."""

from __future__ import annotations

from tqdm import tqdm

from src.data_collection.client import CDGClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_congress_details(client: CDGClient, congress: int):
    """Retrieve detailed information for a specified Congress."""
    return client.get(f"congress/{congress}")


def get_current_congress(client: CDGClient):
    """Retrieve detailed information for the current Congress."""
    return client.get("congress/current")


def gather_congresses(client: CDGClient) -> list:
    """Gather metadata for all Congresses up to the current one."""
    congresses = []
    current_congress_id = client.get("congress/current")["congress"]["number"]
    for i in tqdm(range(1, current_congress_id + 1)):
        congresses.append(client.get(f"congress/{i}")["congress"])
    return congresses


# Alias for single congress retrieval for naming consistency
def get_congress(client: CDGClient, congress: int):
    """Retrieve detailed information for a specified Congress (alias for get_congress_details)."""
    return get_congress_details(client, congress)

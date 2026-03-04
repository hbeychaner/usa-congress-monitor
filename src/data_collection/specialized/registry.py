"""Registry of specialized sync handlers."""

from __future__ import annotations

from typing import Awaitable, Callable, Dict

from elasticsearch import AsyncElasticsearch

from src.data_collection.client import CDGClient
from src.data_collection.specialized.congresses import sync_congresses
from src.data_collection.specialized.members import sync_members
from src.data_collection.specialized.bills import sync_bills
from src.data_collection.specialized.laws import sync_laws
from src.data_collection.specialized.amendments import sync_amendments

SyncHandler = Callable[[CDGClient, AsyncElasticsearch], Awaitable[dict]]

REGISTRY: Dict[str, SyncHandler] = {
    "amendment": sync_amendments,
    "congress": sync_congresses,
    "member": sync_members,
    "bill": sync_bills,
    "law": sync_laws,
}

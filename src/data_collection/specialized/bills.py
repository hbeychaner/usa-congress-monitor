"""Sync bill records with Elasticsearch using a state index."""

from __future__ import annotations

from typing import Any

from elasticsearch import Elasticsearch
from src.data_collection.specialized.common import PaginatedSyncSpec, sync_paginated_index
from knowledgebase.ids import bill_id
from knowledgebase.indices import BILLS_MAPPING
from src.data_collection.client import CDGClient
from src.data_collection.endpoints.bills import get_bills_metadata
from src.utils.logger import get_logger

logger = get_logger(__name__)

INDEX_NAME = "congress-bills"
ENDPOINT_NAME = "bill"


def sync_bills(cdg_client: CDGClient, es_client: Elasticsearch) -> dict[str, Any]:
    """Sync bill records and update state in Elasticsearch."""
    spec = PaginatedSyncSpec(
        index_name=INDEX_NAME,
        endpoint=ENDPOINT_NAME,
        mapping=BILLS_MAPPING,
        data_key="bills",
        id_builder=bill_id,
        page_size=250,
        chunk_size=200,
        progress_desc="Bills pages",
        progress_unit="page",
    )

    result = sync_paginated_index(
        es_client,
        fetch_page=lambda offset, page_size: get_bills_metadata(
            cdg_client, offset=offset, limit=page_size
        ),
        spec=spec,
    )

    logger.info("Sync result: %s", result)
    return result

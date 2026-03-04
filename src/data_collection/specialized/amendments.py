"""Sync amendment records with Elasticsearch using a state index."""

from __future__ import annotations

from typing import Any

from elasticsearch import Elasticsearch

from knowledgebase.ids import amendment_id
from knowledgebase.indices import AMENDMENTS_MAPPING
from src.data_collection.client import CDGClient
from src.data_collection.endpoints.amendments import get_amendments_metadata_paginated
from src.data_collection.specialized.common import PaginatedSyncSpec, sync_paginated_index
from src.utils.logger import get_logger

logger = get_logger(__name__)

INDEX_NAME = "congress-amendments"
ENDPOINT_NAME = "amendment"


def sync_amendments(cdg_client: CDGClient, es_client: Elasticsearch) -> dict[str, Any]:
    """Sync amendment records and update state in Elasticsearch."""
    spec = PaginatedSyncSpec(
        index_name=INDEX_NAME,
        endpoint=ENDPOINT_NAME,
        mapping=AMENDMENTS_MAPPING,
        data_key="amendments",
        id_builder=amendment_id,
        page_size=250,
        chunk_size=200,
        progress_desc="Amendments pages",
        progress_unit="page",
    )

    result = sync_paginated_index(
        es_client,
        fetch_page=lambda offset, page_size: get_amendments_metadata_paginated(
            cdg_client, offset=offset, limit=page_size
        ),
        spec=spec,
    )

    logger.info("Sync result: %s", result)
    return result

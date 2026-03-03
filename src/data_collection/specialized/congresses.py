"""Sync Congress records with Elasticsearch using a state index."""

from __future__ import annotations

from typing import Any

from elasticsearch import Elasticsearch

from knowledgebase.ids import congress_id
from knowledgebase.indices import CONGRESSES_MAPPING
from src.data_collection.client import CDGClient
from src.data_collection.endpoints.congress import gather_congresses
from src.data_collection.specialized.common import (
    sync_records,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

INDEX_NAME = "congress-congresses"
ENDPOINT_NAME = "congress"


def _current_total(client: CDGClient) -> int:
    current = client.get("congress/current").get("congress", {})
    return int(current.get("number", 0))


def sync_congresses(cdg_client: CDGClient, es_client: Elasticsearch) -> dict[str, Any]:
    """Sync congress records and update state in Elasticsearch."""
    current_total = _current_total(cdg_client)
    records = gather_congresses(cdg_client)
    result = sync_records(
        es_client,
        index_name=INDEX_NAME,
        endpoint=ENDPOINT_NAME,
        mapping=CONGRESSES_MAPPING,
        records=records,
        id_builder=congress_id,
        current_total=current_total,
        chunk_size=100,
    )

    logger.info("Congress total from API: %s", current_total)
    logger.info("Sync result: %s", result)
    return result

"""Sync member records with Elasticsearch using a state index."""

from __future__ import annotations

from typing import Any

from elasticsearch import Elasticsearch
from src.data_collection.specialized.common import PaginatedSyncSpec, sync_paginated_index
from knowledgebase.ids import member_id
from knowledgebase.indices import MEMBERS_MAPPING
from src.data_collection.client import CDGClient
from src.data_collection.endpoints.member import get_members_list
from src.utils.logger import get_logger

logger = get_logger(__name__)

INDEX_NAME = "congress-members"
ENDPOINT_NAME = "member"


def sync_members(cdg_client: CDGClient, es_client: Elasticsearch) -> dict[str, Any]:
    """Sync member records and update state in Elasticsearch."""
    spec = PaginatedSyncSpec(
        index_name=INDEX_NAME,
        endpoint=ENDPOINT_NAME,
        mapping=MEMBERS_MAPPING,
        data_key="members",
        id_builder=member_id,
        page_size=250,
        chunk_size=200,
        progress_desc="Members pages",
        progress_unit="page",
    )

    result = sync_paginated_index(
        es_client,
        fetch_page=lambda offset, page_size: get_members_list(
            cdg_client, offset=offset, pageSize=page_size
        ),
        spec=spec,
    )

    logger.info("Sync result: %s", result)
    return result

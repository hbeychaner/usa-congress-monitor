"""Sync law records with Elasticsearch using a state index."""

from __future__ import annotations

from typing import Any

from elasticsearch import Elasticsearch
from tqdm import tqdm

from src.data_collection.specialized.common import (
    PaginatedSyncSpec,
    existing_ids,
    sync_paginated_index,
)
from knowledgebase.ids import law_id
from knowledgebase.indices import LAWS_MAPPING
from src.data_collection.client import CDGClient
from src.data_collection.endpoints.laws import get_laws
INDEX_NAME = "congress-laws"
ENDPOINT_NAME = "law"


def _current_congress(client: CDGClient) -> int:
    current = client.get("congress/current").get("congress", {})
    return int(current.get("number", 0))


def sync_laws(cdg_client: CDGClient, es_client: Elasticsearch) -> dict[str, Any]:
    """Sync law records and update state in Elasticsearch."""
    spec = PaginatedSyncSpec(
        index_name=INDEX_NAME,
        endpoint=ENDPOINT_NAME,
        mapping=LAWS_MAPPING,
        data_key="bills",
        id_builder=law_id,
        page_size=250,
        chunk_size=200,
        progress_desc="Laws pages",
        progress_unit="page",
    )
    existing = existing_ids(es_client, INDEX_NAME)
    current_congress = _current_congress(cdg_client)

    total_indexed = 0
    total_missing = 0
    all_errors: list[dict[str, Any]] = []

    congress_range = range(1, current_congress + 1)
    for congress in tqdm(congress_range, desc="Laws congresses", unit="congress"):
        state_id = f"{INDEX_NAME}:{congress}"
        result = sync_paginated_index(
            es_client,
            fetch_page=lambda offset, page_size: get_laws(
                cdg_client,
                congress=congress,
                offset=offset,
                limit=page_size,
            ),
            spec=spec,
            state_id=state_id,
            existing=existing,
            compare_index_count=False,
        )

        total_indexed += int(result.get("indexed", 0))
        total_missing += int(result.get("missing", 0))
        all_errors.extend(result.get("errors", []))

    return {
        "indexed": total_indexed,
        "missing": total_missing,
        "current_total": None,
        "previous_total": None,
        "errors": all_errors,
    }

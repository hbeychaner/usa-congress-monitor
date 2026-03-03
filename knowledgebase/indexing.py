"""Indexing helpers for loading knowledgebase data into Elasticsearch."""

from __future__ import annotations

from typing import Any, Iterable, cast

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk


def build_actions(
    index_name: str,
    records: Iterable[dict[str, Any]],
    id_builder,
) -> list[dict[str, Any]]:
    """Prepare bulk actions for Elasticsearch."""
    actions: list[dict[str, Any]] = []
    for record in records:
        record_id = id_builder(record)
        if not record_id:
            continue
        record["id"] = record_id
        actions.append(
            {
                "_op_type": "index",
                "_index": index_name,
                "_id": record_id,
                "_source": record,
            }
        )
    return actions


def index_records(
    client: Elasticsearch,
    index_name: str,
    records: list[dict[str, Any]],
    id_builder,
    chunk_size: int = 500,
    request_timeout: int = 300,
) -> tuple[int, list[dict[str, Any]]]:
    """Bulk index records and return (indexed_count, errors)."""
    actions = build_actions(index_name, records, id_builder)
    if not actions:
        return 0, []
    bulk_client = client.options(request_timeout=request_timeout)
    success, errors = bulk(
        bulk_client,
        actions,
        chunk_size=chunk_size,
        max_retries=3,
        initial_backoff=1,
        max_backoff=30,
        raise_on_error=False,
        raise_on_exception=False,
    )
    if isinstance(errors, int):
        return success, []
    return success, cast(list[dict[str, Any]], errors)

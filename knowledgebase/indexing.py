"""Indexing helpers for loading knowledgebase data into Elasticsearch."""

from __future__ import annotations

from typing import Any, Iterable, cast

from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk
import datetime

try:
    # pydantic v1/v2 compatibility: HttpUrl is in pydantic.networks
    from pydantic.networks import HttpUrl  # type: ignore
except Exception:
    HttpUrl = None


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

        def _sanitize(obj: Any) -> Any:
            if obj is None:
                return None
            if isinstance(obj, (str, int, float, bool)):
                return obj
            if isinstance(obj, (datetime.datetime, datetime.date)):
                return obj.isoformat()
            # pydantic HttpUrl -> str
            try:
                if HttpUrl is not None and isinstance(obj, HttpUrl):
                    return str(obj)
            except Exception:
                pass
            if isinstance(obj, dict):
                return {k: _sanitize(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_sanitize(v) for v in obj]
            try:
                return str(obj)
            except Exception:
                return None

        safe_record = _sanitize(record)
        actions.append(
            {
                "_op_type": "index",
                "_index": index_name,
                "_id": record_id,
                "_source": safe_record,
            }
        )
    return actions


async def index_records(
    client: AsyncElasticsearch,
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
    success, errors = await async_bulk(
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

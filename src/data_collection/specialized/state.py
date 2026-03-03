"""Elasticsearch-backed state tracking for sync operations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from elasticsearch import Elasticsearch

STATE_INDEX = "kb-tracking"

STATE_MAPPING: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": True,
        "properties": {
            "index": {"type": "keyword"},
            "endpoint": {"type": "keyword"},
            "total": {"type": "integer"},
            "indexed": {"type": "integer"},
            "updated_at": {"type": "date"},
            "offset": {"type": "integer"},
            "page": {"type": "integer"},
            "page_size": {"type": "integer"},
            "pages": {"type": "integer"},
            "status": {"type": "keyword"},
            "index_name": {"type": "alias", "path": "index"},
            "last_total": {"type": "alias", "path": "total"},
            "last_index_count": {"type": "alias", "path": "indexed"},
            "last_run": {"type": "alias", "path": "updated_at"},
            "last_offset": {"type": "alias", "path": "offset"},
            "last_page": {"type": "alias", "path": "page"},
            "total_pages": {"type": "alias", "path": "pages"},
        },
    },
}


def ensure_state_index(client: Elasticsearch) -> None:
    if client.indices.exists(index=STATE_INDEX):
        return
    legacy_index = "kb-sync-state"
    if client.indices.exists(index=legacy_index):
        client.indices.put_mapping(
            index=legacy_index,
            properties=STATE_MAPPING.get("mappings", {}).get("properties", {}),
        )
        if not client.indices.exists_alias(name=STATE_INDEX):
            client.indices.put_alias(index=legacy_index, name=STATE_INDEX)
        return
    client.indices.create(
        index=STATE_INDEX,
        settings=STATE_MAPPING.get("settings", {}),
        mappings=STATE_MAPPING.get("mappings", {}),
    )


def _normalize_state(source: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(source)
    if "index" not in normalized and "index_name" in normalized:
        normalized["index"] = normalized.get("index_name")
    if "total" not in normalized and "last_total" in normalized:
        normalized["total"] = normalized.get("last_total")
    if "indexed" not in normalized and "last_index_count" in normalized:
        normalized["indexed"] = normalized.get("last_index_count")
    if "updated_at" not in normalized and "last_run" in normalized:
        normalized["updated_at"] = normalized.get("last_run")
    if "offset" not in normalized and "last_offset" in normalized:
        normalized["offset"] = normalized.get("last_offset")
    if "page" not in normalized and "last_page" in normalized:
        normalized["page"] = normalized.get("last_page")
    if "pages" not in normalized and "total_pages" in normalized:
        normalized["pages"] = normalized.get("total_pages")
    return normalized


def get_state(client: Elasticsearch, state_id: str) -> dict[str, Any]:
    ensure_state_index(client)
    try:
        response = client.get(index=STATE_INDEX, id=state_id)
    except Exception:
        return {}
    return _normalize_state(dict(response.get("_source", {})))


def upsert_state(
    client: Elasticsearch,
    state_id: str,
    endpoint: str,
    *,
    index: str,
    total: int,
    indexed: int,
    offset: int | None = None,
    page: int | None = None,
    page_size: int | None = None,
    pages: int | None = None,
    status: str | None = None,
) -> None:
    ensure_state_index(client)
    body = {
        "index": index,
        "endpoint": endpoint,
        "total": total,
        "indexed": indexed,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if offset is not None:
        body["offset"] = offset
    if page is not None:
        body["page"] = page
    if page_size is not None:
        body["page_size"] = page_size
    if pages is not None:
        body["pages"] = pages
    if status is not None:
        body["status"] = status
    client.index(index=STATE_INDEX, id=state_id, document=body)

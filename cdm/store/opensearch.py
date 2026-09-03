"""OpenSearch index management and bulk upsert helpers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast

INDEX_PREFIX = "congress"

# Source resources that share a physical index must carry a discriminator in
# the document so queries can distinguish their source shapes.
_RESOURCE_TARGETS: dict[str, tuple[str, dict[str, str]]] = {
    "bill": ("legislation", {"source_type": "bill"}),
    "bill_text": ("legislation", {"source_type": "bill_text"}),
    "law": ("legislation", {"source_type": "law"}),
    "house_communication": ("communication", {"chamber": "House"}),
    "senate_communication": ("communication", {"chamber": "Senate"}),
    "bound_congressional_record": (
        "congressional_record",
        {"record_subtype": "bound"},
    ),
    "daily_congressional_record": (
        "congressional_record",
        {"record_subtype": "daily"},
    ),
    "congress": ("congress_ref", {}),
    "district": ("district", {}),
}


def resource_target(resource: str) -> tuple[str, dict[str, str]]:
    """Return the logical index and discriminator fields for a resource."""
    if resource == "summaries":
        raise ValueError(
            "summaries are denormalized into legislation and cannot be indexed directly"
        )
    return _RESOURCE_TARGETS.get(resource, (resource, {}))


def index_name(resource: str) -> str:
    """Return the canonical OpenSearch index name for *resource*."""
    target, _ = resource_target(resource)
    return f"{INDEX_PREFIX}-{target.replace('_', '-')}"


def write_alias(resource: str) -> str:
    return f"{index_name(resource)}-write"


def read_alias(resource: str) -> str:
    return f"{index_name(resource)}-read"


def bulk_upsert(
    client: Any,
    resource: str,
    docs: Iterable[dict],
    *,
    target_index: str | None = None,
    replace: bool = False,
) -> dict:
    """Upsert records, or replace complete documents when ``replace`` is true."""
    from elasticsearch.helpers import bulk

    documents = list(docs)
    index = target_index or write_alias(resource)
    merge_script = (
        "for (entry in params.doc.entrySet()) {"
        " def key = entry.getKey();"
        " def value = entry.getValue();"
        " if (value != null) {"
        "  if (value instanceof List) {"
        "   if (!value.isEmpty()) {"
        "    if (ctx._source[key] == null) { ctx._source[key] = value; }"
        "    else {"
        "     if (!(ctx._source[key] instanceof List)) { ctx._source[key] = [ctx._source[key]]; }"
        "     for (item in value) {"
        "      if (!ctx._source[key].contains(item)) { ctx._source[key].add(item); }"
        "     }"
        "    }"
        "   }"
        "  } else if (value instanceof Map && ctx._source[key] instanceof Map) {"
        "   ctx._source[key].putAll(value);"
        "  } else if (!(value instanceof String && value.isEmpty())) {"
        "   ctx._source[key] = value;"
        "  }"
        " }"
        "}"
    )
    actions = []
    for doc in documents:
        if not doc.get("id"):
            continue
        if replace:
            actions.append({
                "_op_type": "index",
                "_index": index,
                "_id": doc["id"],
                "_source": doc,
            })
        elif resource == "bill":
            actions.append({
                "_op_type": "update",
                "_index": index,
                "_id": doc["id"],
                "script": {
                    "lang": "painless",
                    "source": merge_script,
                    "params": {"doc": doc},
                },
                "upsert": doc,
                "scripted_upsert": True,
            })
        else:
            actions.append({
                "_op_type": "update",
                "_index": index,
                "_id": doc["id"],
                "doc": doc,
                "doc_as_upsert": True,
            })
    if not actions:
        return {
            "updated": 0,
            "errors": False,
            "skipped_missing_ids": len(documents),
        }

    success, errors = bulk(client, actions, raise_on_error=False)
    errors = cast(list[dict[str, Any]], errors)
    result = {
        "updated": success,
        "errors": bool(errors),
        "skipped_missing_ids": sum(1 for doc in documents if not doc.get("id")),
    }
    if errors:
        result["error_details"] = errors[:3]
    return result

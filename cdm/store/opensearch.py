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


# Later stages of the legislative text lifecycle rank higher.
TEXT_VERSION_RANKS = {
    "ih": 0,
    "is": 0,
    "rh": 1,
    "rs": 1,
    "rds": 1,
    "rcs": 1,
    "pcs": 1,
    "eh": 2,
    "es": 2,
    "eas": 2,
    "enr": 3,
}

# Applies a bill-text record to its parent bill: identity fields fill only
# when absent, and full_text is replaced only by an equal-or-later version
# (API-hydrated text, which carries no rank, is never overwritten).
_TEXT_MERGE_SCRIPT = (
    "for (entry in params.base.entrySet()) {"
    " if (ctx._source[entry.getKey()] == null) {"
    "  ctx._source[entry.getKey()] = entry.getValue();"
    " }"
    "}"
    "def existing = ctx._source['full_text_version_rank'];"
    "if (ctx._source['full_text'] == null"
    "    || (existing != null && params.rank >= ((Number) existing).intValue())) {"
    " ctx._source['full_text'] = params.full_text;"
    " ctx._source['full_text_version_code'] = params.version_code;"
    " ctx._source['full_text_version_rank'] = params.rank;"
    "}"
)


def bill_text_parent_action(
    doc: dict, index: str
) -> dict[str, Any] | None:
    """Return the parent-bill update action for a bill-text record."""
    congress = doc.get("congress")
    bill_type = str(doc.get("type") or "").lower()
    number = doc.get("number")
    full_text = doc.get("full_text")
    if not (congress and bill_type and number and full_text):
        return None
    version_code = str(doc.get("version_code") or "").lower()
    bill_id = f"bill:{congress}:{bill_type}:{number}"
    base = {
        "id": bill_id,
        "congress": congress,
        "type": bill_type,
        "number": str(number),
        "source_type": "bill",
        "_resource": "bill",
    }
    return {
        "_op_type": "update",
        "_index": index,
        "_id": bill_id,
        "script": {
            "lang": "painless",
            "source": _TEXT_MERGE_SCRIPT,
            "params": {
                "base": base,
                "rank": TEXT_VERSION_RANKS.get(version_code, 0),
                "full_text": full_text,
                "version_code": version_code,
            },
        },
        "upsert": {},
        "scripted_upsert": True,
    }


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
        elif resource == "bill_text":
            action = bill_text_parent_action(doc, index)
            if action is not None:
                actions.append(action)
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

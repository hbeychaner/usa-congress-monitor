"""OpenSearch index management and bulk upsert helpers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

INDEX_PREFIX = "congress"

# Source resources that share a physical index must carry a discriminator in
# the document so queries can distinguish their source shapes.
_RESOURCE_TARGETS: dict[str, tuple[str, dict[str, str]]] = {
    "bill": ("legislation", {"source_type": "bill"}),
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
    return index_name(resource)


def bulk_upsert(client: Any, resource: str, docs: Iterable[dict]) -> dict:
    """Upsert *docs* into the OpenSearch index for *resource*.

    Each doc must have an ``id`` field which becomes the document ``_id``.
    Uses the ``_update`` API with ``doc_as_upsert=True`` for idempotency.

    Parameters
    ----------
    client:
        A connected ``elasticsearch.Elasticsearch`` instance.
    resource:
        Logical resource name (e.g. ``"legislation"``).  The full index name
        is resolved via :func:`write_alias`.
    docs:
        Iterable of dicts; each must contain an ``"id"`` key.

    Returns
    -------
    dict
        ``{"updated": int, "errors": bool}``
    """
    from elasticsearch.helpers import bulk

    documents = list(docs)
    index = write_alias(resource)
    actions = [
        {
            "_op_type": "update",
            "_index": index,
            "_id": doc["id"],
            "doc": doc,
            "doc_as_upsert": True,
        }
        for doc in documents
        if doc.get("id")
    ]
    if not actions:
        return {
            "updated": 0,
            "errors": False,
            "skipped_missing_ids": len(documents),
        }

    success, errors = bulk(client, actions, raise_on_error=False)
    return {
        "updated": success,
        "errors": bool(errors),
        "skipped_missing_ids": sum(1 for doc in documents if not doc.get("id")),
    }

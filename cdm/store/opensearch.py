"""OpenSearch index management and bulk upsert helpers."""

from __future__ import annotations

from typing import Any, Iterable

INDEX_PREFIX = "congress"


def index_name(resource: str) -> str:
    """Return the canonical OpenSearch index name for *resource*."""
    return f"{INDEX_PREFIX}-{resource.replace('_', '-')}"


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

    index = write_alias(resource)
    actions = [
        {
            "_op_type": "update",
            "_index": index,
            "_id": doc["id"],
            "doc": doc,
            "doc_as_upsert": True,
        }
        for doc in docs
        if doc.get("id")
    ]
    if not actions:
        return {"updated": 0, "errors": False}

    success, errors = bulk(client, actions, raise_on_error=False)
    return {"updated": success, "errors": bool(errors)}

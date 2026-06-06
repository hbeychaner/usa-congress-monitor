"""Transform ingested model dicts into OpenSearch documents.

The indexer is the boundary between the congress_sdk models and the CDM
storage layer. It may enrich, normalise, or flatten fields before indexing.
"""

from __future__ import annotations

from typing import Any


def to_document(record: dict, resource: str) -> dict:
    """Return an OS-ready document for *record* from *resource*.

    Adds ``_resource`` metadata and ensures the ``id`` field is present.
    Raw nested payloads are preserved under ``_raw`` when the record
    contains one (set by IngestRunner when ``save_raw_items=True``).
    """
    doc = dict(record)
    doc.setdefault("_resource", resource)
    return doc

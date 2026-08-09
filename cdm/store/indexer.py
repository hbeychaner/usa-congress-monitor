"""Transform ingested model dicts into OpenSearch documents.

The indexer is the boundary between the cdm models and the CDM
storage layer. It may enrich, normalise, or flatten fields before indexing.
"""

from __future__ import annotations

from cdm.data_collection.id_utils import parse_url_to_id
from cdm.store.opensearch import resource_target


def to_document(
    record: dict,
    resource: str,
    *,
    raw_record: dict | None = None,
    preserve_raw: bool = False,
) -> dict:
    """Return an OS-ready document for *record* from *resource*.

    Adds ``_resource`` metadata and ensures the ``id`` field is present.
    Raw nested payloads may be preserved under ``_raw`` when supplied by a
    caller that retains the original API payload.
    """
    _, metadata = resource_target(resource)
    doc = {**record, **metadata}
    if not doc.get("id"):
        if not doc.get("url"):
            raise ValueError(f"Cannot index {resource} record without id or url")
        doc["id"] = parse_url_to_id(str(doc["url"]))

    reference_id = doc.get("reference_id") or doc.get("referenceId")
    doc.pop("referenceId", None)
    if reference_id:
        doc["reference_id"] = str(reference_id)

    if preserve_raw and raw_record is not None:
        doc["_raw"] = dict(raw_record)

    doc.setdefault("_resource", resource)
    return doc

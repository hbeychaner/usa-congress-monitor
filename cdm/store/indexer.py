"""Transform ingested model dicts into OpenSearch documents.

The indexer is the boundary between the cdm models and the CDM
storage layer. It may enrich, normalise, or flatten fields before indexing.
"""

from __future__ import annotations

from collections.abc import Mapping

from cdm.data_collection.id_utils import parse_url_to_id
from cdm.store.opensearch import resource_target


def _bioguide_ids(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        str(member.get("bioguide_id") or member.get("bioguideId"))
        for member in value
        if isinstance(member, dict)
        and (member.get("bioguide_id") or member.get("bioguideId"))
    ]


def to_document(
    record: dict,
    resource: str,
    *,
    raw_record: dict | None = None,
    preserve_raw: bool = False,
    ingest_metadata: Mapping[str, object] | None = None,
) -> dict:
    """Return an OS-ready document for *record* from *resource*.

    Adds ``_resource`` metadata and ensures the ``id`` field is present.
    Raw nested payloads may be preserved under ``_raw`` when supplied by a
    caller that retains the original API payload.
    """
    _, metadata = resource_target(resource)
    doc = {**record, **metadata}
    if ingest_metadata:
        doc.update(dict(ingest_metadata))
    if not doc.get("id"):
        if not doc.get("url"):
            raise ValueError(f"Cannot index {resource} record without id or url")
        doc["id"] = parse_url_to_id(str(doc["url"]))

    reference_id = doc.get("reference_id") or doc.get("referenceId")
    doc.pop("referenceId", None)
    if reference_id:
        doc["reference_id"] = str(reference_id)

    if resource == "bill":
        doc["sponsor_bioguide_ids"] = _bioguide_ids(doc.get("sponsors"))
        doc["cosponsor_bioguide_ids"] = _bioguide_ids(doc.get("cosponsors"))
        source_metadata = doc.get("source_metadata")
        if isinstance(source_metadata, dict):
            doc["source_metadata"] = [source_metadata]
            for field, metadata_key in (
                ("source_package_ids", "package_id"),
                ("source_urls", "url"),
            ):
                value = source_metadata.get(metadata_key)
                if value:
                    doc[field] = [str(value)]

    if preserve_raw and raw_record is not None:
        doc["_raw"] = dict(raw_record)

    doc.setdefault("_resource", resource)
    return doc

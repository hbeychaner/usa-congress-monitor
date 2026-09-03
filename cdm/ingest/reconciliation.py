"""Reconcile official bill records into complete, provenance-aware documents."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from cdm.ingest.archive import SQLiteRecordArchive
from cdm.store.indexer import to_document
from cdm.store.mapping_validation import validate_document
from cdm.store.opensearch import bulk_upsert

_SOURCE_PRIORITY = {
    "govinfo:billstatus": 0,
    "govinfo:billsum": 1,
    "congress.gov_api": 2,
}
_IDENTITY_FIELDS = {"id", "source_metadata", "reconciliation"}
_LIST_FIELDS = {
    "actions",
    "amendments",
    "committees",
    "cosponsors",
    "laws",
    "related_bills",
    "subjects",
    "summaries",
    "text_versions",
    "titles",
}


def _source_entries(record: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = record.get("source_metadata", [])
    if isinstance(metadata, dict):
        return [metadata]
    if isinstance(metadata, list):
        return [entry for entry in metadata if isinstance(entry, dict)]
    return []


def _source_name(record: dict[str, Any]) -> str:
    return str((_source_entries(record) or [{}])[0].get("source", "unknown"))


def _value_key(value: Any) -> str:
    if isinstance(value, dict):
        return repr(sorted((key, _value_key(item)) for key, item in value.items()))
    return repr(value)


def reconcile_bill_sources(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Merge parent bill records and report conflicts and source coverage.

    Records must already be parsed by an official adapter. Empty values never
    replace non-empty values, and all source metadata is retained in the result.
    Text-version records (whose IDs start with ``bill-text:``) are not merged
    into parents; they remain independently indexable child records.
    """
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    skipped = 0
    for record in records:
        record_id = str(record.get("id", ""))
        if not record_id or record_id.startswith("bill-text:"):
            skipped += 1
            continue
        grouped[record_id].append(record)

    reconciled: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for record_id, candidates in sorted(grouped.items()):
        ordered = sorted(
            candidates,
            key=lambda item: _SOURCE_PRIORITY.get(_source_name(item), 99),
        )
        merged: dict[str, Any] = {"id": record_id}
        field_sources: dict[str, str] = {}
        sources: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []

        for candidate in ordered:
            sources.extend(_source_entries(candidate))
            for field, value in candidate.items():
                if field in _IDENTITY_FIELDS or value in (None, "", [], {}):
                    continue
                if field in _LIST_FIELDS and isinstance(value, list):
                    existing = merged.setdefault(field, [])
                    field_sources.setdefault(field, _source_name(candidate))
                    for item in value:
                        if item not in existing:
                            existing.append(item)
                    continue
                if field not in merged:
                    merged[field] = value
                    field_sources[field] = _source_name(candidate)
                elif merged[field] != value:
                    conflicts.append({
                        "field": field,
                        "selected": merged[field],
                        "discarded": value,
                        "selected_source": field_sources[field],
                        "discarded_source": _source_name(candidate),
                    })

        unique_sources = []
        seen_sources: set[str] = set()
        for source in sources:
            source_key = _value_key(source)
            if source_key not in seen_sources:
                unique_sources.append(source)
                seen_sources.add(source_key)
        merged["source_metadata"] = unique_sources
        merged["source_package_ids"] = sorted({
            str(source["package_id"])
            for source in unique_sources
            if source.get("package_id")
        })
        merged["source_urls"] = sorted({
            str(source["url"]) for source in unique_sources if source.get("url")
        })
        merged["reconciliation"] = {
            "status": "complete" if len(ordered) > 1 else "single_source",
            "sources": sorted({_source_name(candidate) for candidate in ordered}),
            "source_count": len(ordered),
            "conflicts": conflicts,
        }
        reconciled.append(merged)
        diagnostics.append({
            "id": record_id,
            "source_count": len(ordered),
            "conflict_count": len(conflicts),
            "conflicts": conflicts,
        })

    return {
        "records": reconciled,
        "diagnostics": diagnostics,
        "input_count": sum(len(items) for items in grouped.values()) + skipped,
        "parent_count": len(reconciled),
        "skipped_count": skipped,
    }


def replay_govinfo_archives(
    archive_root: Path,
    client: Any,
    *,
    target_index: str,
    report_path: Path,
    preserve_raw: bool = True,
) -> dict[str, Any]:
    """Reconcile every package archive below *archive_root* into staging."""
    archive_paths = sorted(archive_root.glob("*/records.sqlite3"))
    if not archive_paths:
        raise ValueError(f"No package archives found below {archive_root}")

    parent_records: list[dict[str, Any]] = []
    text_records: list[dict[str, Any]] = []
    for archive_path in archive_paths:
        archive = SQLiteRecordArchive(archive_path.parent, 0)
        parent_records.extend(archive.records("bill"))
        text_records.extend(archive.records("bill_text"))

    reconciliation = reconcile_bill_sources(parent_records)
    quarantine: list[dict[str, str]] = []
    parent_documents: list[dict[str, Any]] = []
    for record in reconciliation["records"]:
        try:
            document = to_document(record, "bill", preserve_raw=preserve_raw)
            validate_document(document, "bill")
        except (TypeError, ValueError) as exc:
            quarantine.append({
                "resource": "bill",
                "id": str(record.get("id", "")),
                "reason": str(exc),
            })
            continue
        parent_documents.append(document)

    valid_text_documents: list[dict[str, Any]] = []
    for record in text_records:
        try:
            document = to_document(record, "bill_text", preserve_raw=preserve_raw)
            validate_document(document, "bill_text")
        except (TypeError, ValueError) as exc:
            quarantine.append({
                "resource": "bill_text",
                "id": str(record.get("id", "")),
                "reason": str(exc),
            })
            continue
        valid_text_documents.append(document)

    parent_write = bulk_upsert(
        client,
        "bill",
        parent_documents,
        target_index=target_index,
        replace=True,
    )
    text_write = bulk_upsert(
        client,
        "bill_text",
        valid_text_documents,
        target_index=target_index,
        replace=True,
    )
    write_result = {"parents": parent_write, "text_versions": text_write}
    report = {
        "archive_count": len(archive_paths),
        "parent_input_count": len(parent_records),
        "parent_count": len(parent_documents),
        "reconciled_parent_count": len(reconciliation["records"]),
        "text_version_count": len(valid_text_documents),
        "document_count": len(parent_documents) + len(valid_text_documents),
        "quarantine_count": len(quarantine),
        "quarantine": quarantine,
        "diagnostics": reconciliation["diagnostics"],
        "write": write_result,
        "audited": len(parent_documents) + len(valid_text_documents),
        "status": "completed",
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if parent_write.get("errors") or text_write.get("errors"):
        raise RuntimeError(f"Reconciliation indexing failed: {write_result}")
    return report

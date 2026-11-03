"""Reconcile official bill records into complete, provenance-aware documents."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from elasticsearch import Elasticsearch
from pydantic import AwareDatetime, BaseModel, Field, TypeAdapter, ValidationError

from cdm.config.source_policy import FieldName, SourceName, SourcePolicy
from cdm.ingest.archive import SQLiteRecordArchive
from cdm.ingest.full_ingest import FullIngestConfig
from cdm.ingest.resource_config import RESOURCE_CONFIGS
from cdm.ingest.source_contract import (
    BillCandidate,
    CoverageState,
    FieldConflict,
    ReconciliationEvidence,
    ResourceCoverage,
    SnapshotEvidence,
    SourceCheck,
    SourceMetadata,
    StageCoverage,
)
from cdm.store.indexer import to_document
from cdm.store.mapping_validation import validate_document
from cdm.store.opensearch import bulk_upsert
from cdm.utils.json_types import JsonObject
from cdm.workers.planners import congress_for_year


class ReconciliationDiagnostic(BaseModel):
    id: str
    source_count: int
    conflict_count: int
    conflicts: list[FieldConflict]


class ReconciliationResult(BaseModel):
    records: list[JsonObject] = Field(default_factory=list)
    diagnostics: list[ReconciliationDiagnostic] = Field(default_factory=list)
    input_count: int = 0
    parent_count: int = 0
    skipped_count: int = 0
    source_checks: dict[str, AwareDatetime] = Field(default_factory=dict)
    source_errors: list[QuarantinedRecord] = Field(default_factory=list)


class TargetAliases(BaseModel):
    aliases: JsonObject


class TargetMapping(BaseModel):
    properties: dict[FieldName, JsonObject] = Field(default_factory=dict)


class TargetDefinition(BaseModel):
    mappings: TargetMapping


class TargetCount(BaseModel):
    count: int


class TargetInventory(BaseModel):
    requested: str
    physical_indices: list[str]
    aliases: list[str]
    mapped_fields: list[FieldName]
    existing_documents: int

    @classmethod
    def read(cls, client: Elasticsearch, target: str) -> TargetInventory:
        if not client.indices.exists(index=target):
            raise ValueError(f"Explicit index target does not exist: {target!r}")
        aliases = TypeAdapter(dict[str, TargetAliases]).validate_python(
            client.indices.get_alias(index=target).body
        )
        mappings = TypeAdapter(dict[str, TargetDefinition]).validate_python(
            client.indices.get_mapping(index=target).body
        )
        return cls(
            requested=target,
            physical_indices=sorted(aliases),
            aliases=sorted(
                {name for value in aliases.values() for name in value.aliases}
            ),
            mapped_fields=sorted(
                {
                    name
                    for value in mappings.values()
                    for name in value.mappings.properties
                }
            ),
            existing_documents=TargetCount.model_validate(
                client.count(index=target).body
            ).count,
        )

    def require_unaliased_staging(self) -> None:
        if self.physical_indices != [self.requested] or self.aliases:
            raise ValueError(
                "Reconciliation writes require an exact, unaliased physical staging index"
            )


class ReplayStatus(StrEnum):
    PREVIEW = "preview"
    COMPLETED = "completed"


class QuarantinedRecord(BaseModel):
    resource: str
    id: str
    reason: str


class BulkResult(BaseModel):
    updated: int
    errors: bool
    skipped_missing_ids: int


class ReplayWrites(BaseModel):
    parents: BulkResult | None
    text_versions: BulkResult | None


class ReplayReport(BaseModel):
    archive_count: int
    archives_read: int
    parent_input_count: int
    parent_count: int
    reconciled_parent_count: int
    text_version_count: int
    document_count: int
    quarantine_count: int
    quarantine: list[QuarantinedRecord]
    diagnostics: list[ReconciliationDiagnostic]
    write: ReplayWrites
    target_inventory: TargetInventory | None
    target_inventory_unavailable_reason: str | None
    archive_fields: list[FieldName]
    sample_limit: int | None
    audited: int
    status: ReplayStatus
    source_coverage: CoverageState
    promotable: bool
    coverage: list[ResourceCoverage]
    required_coverage: list[ResourceCoverage]


class SourceContractError(ValueError):
    """Source evidence is inconsistent; never choose a publishable winner."""


class BillReconciler:
    def __init__(self, policy: SourcePolicy) -> None:
        self.policy = policy
        self._identity = re.compile(policy.bill_id_pattern)
        self._integer = TypeAdapter(int)

    def candidate(self, record: JsonObject) -> BillCandidate:
        match = self._identity.fullmatch(str(record.get("id", "")))
        if match is None:
            raise SourceContractError(
                f"Invalid canonical bill identity: {record.get('id')!r}"
            )
        if int(match[2]) < 1 or int(match[4]) < 1:
            raise SourceContractError(
                "Canonical bill Congress and number must be positive"
            )
        for field, expected in zip(("congress", "type", "number"), match.groups()[1:]):
            value = record.get(field)
            if value is not None and (
                str(value).lower() != expected
                if field == "type"
                else self._integer.validate_python(value) != int(expected)
            ):
                raise SourceContractError(
                    f"Canonical identity collision: {match[1]} disagrees with {field}"
                )
        metadata = record.get("source_metadata", [])
        entries = [metadata] if isinstance(metadata, dict) else metadata
        candidate = BillCandidate(
            id=match[1],
            fields={
                FieldName(key): value
                for key, value in record.items()
                if key not in self.policy.identity_fields
            },
            metadata=[SourceMetadata.model_validate(entry) for entry in entries]
            if isinstance(entries, list)
            else [SourceMetadata.model_validate(entries)],
            snapshot=SnapshotEvidence.model_validate(record["source_snapshot"])
            if "source_snapshot" in record
            else None,
        )
        candidate.checked_at = SourceCheck.model_validate(
            {"fetched_at": record.get("source_checked_at")}
        ).fetched_at
        if candidate.checked_at is None and candidate.snapshot is not None:
            candidate.checked_at = candidate.snapshot.checked_at
        if candidate.snapshot is not None:
            proof = candidate.snapshot
            if (
                candidate.checked_at is not None
                and proof.version > candidate.checked_at
            ):
                raise SourceContractError(
                    "Source version postdates its verified source check"
                )
            if not proof.complete_fields <= candidate.fields.keys():
                raise SourceContractError(
                    f"Snapshot declares absent complete fields: {candidate.id}"
                )
            if candidate.metadata and proof.source not in {
                entry.source for entry in candidate.metadata
            }:
                raise SourceContractError(
                    f"Snapshot source disagrees with provenance: {candidate.id}"
                )
        return candidate

    def reconcile(self, records: Iterable[JsonObject]) -> ReconciliationResult:
        grouped: dict[str, list[BillCandidate]] = defaultdict(list)
        result = ReconciliationResult()
        for record in records:
            result.input_count += 1
            if not record.get("id") or str(record["id"]).startswith("bill-text:"):
                result.skipped_count += 1
                continue
            candidate = self.candidate(record)
            grouped[candidate.id].append(candidate)
        for record_id, candidates in sorted(grouped.items()):
            checks: dict[SourceName, datetime] = {}
            for item in candidates:
                if item.source != SourceName.UNKNOWN and item.checked_at is not None:
                    prior = checks.get(item.source)
                    checks[item.source] = (
                        max(prior, item.checked_at)
                        if prior is not None
                        else item.checked_at
                    )
            if set(checks) == {item.source for item in candidates}:
                result.source_checks[record_id] = min(checks.values())
            introduced = {
                str(item.fields.get(FieldName("introduced_date")))
                for item in candidates
                if item.fields.get(FieldName("introduced_date"))
            }
            if len(introduced) > 1 and any(
                item.snapshot is None
                or FieldName("introduced_date") not in item.snapshot.complete_fields
                for item in candidates
            ):
                raise SourceContractError(
                    f"Canonical identity collision: {record_id} has distinct unverified introduction dates"
                )
            ordered = sorted(
                candidates,
                key=lambda item: json.dumps(
                    item.model_dump(mode="json"), sort_keys=True
                ),
            )
            merged: JsonObject = {"id": record_id}
            evidence = ReconciliationEvidence(
                sources=sorted({item.source for item in ordered}),
                source_count=len(ordered),
                conflicts=[],
            )
            for field in sorted({key for item in ordered for key in item.fields}):
                options = [item for item in ordered if field in item.fields]
                proven = [
                    item
                    for item in options
                    if item.snapshot is not None
                    and field in item.snapshot.complete_fields
                ]
                if proven:
                    rank = min(self.policy.rank(item.source, field) for item in proven)
                    peers = [
                        item
                        for item in proven
                        if self.policy.rank(item.source, field) == rank
                    ]
                    newest = max(
                        item.snapshot.version
                        for item in peers
                        if item.snapshot is not None
                    )
                    peers = [
                        item
                        for item in peers
                        if item.snapshot is not None and item.snapshot.version == newest
                    ]
                    if any(
                        item.fields[field] != peers[0].fields[field] for item in peers
                    ):
                        raise SourceContractError(
                            f"Equal-version source conflict: {record_id} field {field}"
                        )
                    selected = peers[0]
                    assert selected.snapshot is not None
                    evidence.field_authority[field] = selected.snapshot
                    merged[field] = selected.fields[field]
                else:
                    options = [
                        item
                        for item in options
                        if item.fields[field] not in (None, "", [], {})
                    ]
                    if not options:
                        continue
                    selected = min(
                        options, key=lambda item: self.policy.rank(item.source, field)
                    )
                    merged[field] = selected.fields[field]
                    evidence.unverified_fields.append(field)
                    if field in self.policy.list_fields and isinstance(
                        merged[field], list
                    ):
                        values = []
                        for item in options:
                            value = item.fields[field]
                            if isinstance(value, list):
                                for member in value:
                                    if member not in values:
                                        values.append(member)
                        merged[field] = values
                for item in options:
                    if item.fields[field] != merged[field]:
                        evidence.conflicts.append(
                            FieldConflict(
                                field=field,
                                selected=merged[field],
                                discarded=item.fields[field],
                                selected_source=selected.source,
                                discarded_source=item.source,
                            )
                        )
            sources = {
                json.dumps(
                    entry.model_dump(mode="json", exclude_none=True), sort_keys=True
                )
                for item in ordered
                for entry in item.metadata
            }
            merged["source_metadata"] = [json.loads(entry) for entry in sorted(sources)]
            merged["source_package_ids"] = sorted(
                {
                    entry.package_id
                    for item in ordered
                    for entry in item.metadata
                    if entry.package_id
                }
            )
            merged["source_urls"] = sorted(
                {entry.url for item in ordered for entry in item.metadata if entry.url}
            )
            merged["reconciliation"] = evidence.model_dump(mode="json")
            result.records.append(merged)
            result.diagnostics.append(
                ReconciliationDiagnostic(
                    id=record_id,
                    source_count=len(ordered),
                    conflict_count=len(evidence.conflicts),
                    conflicts=evidence.conflicts,
                )
            )
        result.parent_count = len(result.records)
        return result

    def inspect(self, records: Iterable[JsonObject]) -> ReconciliationResult:
        result = ReconciliationResult()
        groups: dict[str, list[JsonObject]] = defaultdict(list)
        for record in records:
            result.input_count += 1
            try:
                candidate = self.candidate(record)
            except (SourceContractError, ValidationError) as exc:
                result.source_errors.append(
                    QuarantinedRecord(
                        resource="bill",
                        id=str(record.get("id", "")),
                        reason=str(exc),
                    )
                )
                continue
            groups[candidate.id].append(record)
        for record_id, group in sorted(groups.items()):
            try:
                accepted = self.reconcile(group)
            except (SourceContractError, ValidationError) as exc:
                result.source_errors.append(
                    QuarantinedRecord(
                        resource="bill",
                        id=record_id,
                        reason=str(exc),
                    )
                )
                continue
            result.records.extend(accepted.records)
            result.diagnostics.extend(accepted.diagnostics)
            result.source_checks.update(accepted.source_checks)
        result.parent_count = len(result.records)
        return result


def reconcile_bill_sources(records: Iterable[JsonObject]) -> JsonObject:
    return BillReconciler(SourcePolicy()).reconcile(records).model_dump(mode="json")


def replay_govinfo_archives(
    archive_root: Path,
    client: Elasticsearch | None,
    *,
    target_index: str | None,
    report_path: Path,
    preserve_raw: bool = True,
    preview: bool = False,
    max_records: int | None = None,
) -> JsonObject:
    """Reconcile every package archive below *archive_root* into staging."""
    history = FullIngestConfig(last_congress=congress_for_year(datetime.now(UTC).year))
    if max_records is not None and (max_records < 1 or not preview):
        raise ValueError(
            "A positive record limit is permitted only for read-only preview"
        )
    archive_paths = sorted(archive_root.glob("*/records.sqlite3"))
    if not archive_paths:
        raise ValueError(f"No package archives found below {archive_root}")
    if any(
        report_path.resolve().is_relative_to(path.parent.resolve())
        for path in archive_paths
    ):
        raise ValueError("The report must be outside source package directories")
    if (client is None) != (target_index is None):
        raise ValueError(
            "Supply both a search client and target index, or neither for archive-only preview"
        )
    inventory = (
        TargetInventory.read(client, target_index)
        if client is not None and target_index is not None
        else None
    )
    if not preview:
        if inventory is None:
            raise ValueError("Staging writes require an inspected search target")
        inventory.require_unaliased_staging()

    parent_records: list[JsonObject] = []
    text_records: list[JsonObject] = []
    archives_read = 0
    for archive_path in archive_paths:
        remaining = (
            None
            if max_records is None
            else max_records - len(parent_records) - len(text_records)
        )
        if remaining == 0:
            break
        archive = SQLiteRecordArchive(archive_path.parent, 0, read_only=True)
        archives_read += 1
        try:
            parent_records.extend(archive.records("bill", limit=remaining))
            remaining = (
                None
                if max_records is None
                else max_records - len(parent_records) - len(text_records)
            )
            text_records.extend(archive.records("bill_text", limit=remaining))
        finally:
            archive.engine.dispose()

    reconciler = BillReconciler(SourcePolicy())
    reconciliation = (
        reconciler.inspect(parent_records)
        if preview
        else reconciler.reconcile(parent_records)
    )
    congresses = {
        int(record["id"].split(":")[1])
        for record in reconciliation.records
        if isinstance(record["id"], str)
    }
    checked_at = (
        min(reconciliation.source_checks.values())
        if reconciliation.parent_count
        and len(reconciliation.source_checks) == reconciliation.parent_count
        else None
    )
    quarantine: list[dict[str, str]] = [
        item.model_dump() for item in reconciliation.source_errors
    ]
    parent_documents: list[JsonObject] = []
    for record in reconciliation.records:
        try:
            document = to_document(record, "bill", preserve_raw=preserve_raw)
            validate_document(document, "bill")
        except (TypeError, ValueError) as exc:
            quarantine.append(
                {
                    "resource": "bill",
                    "id": str(record.get("id", "")),
                    "reason": str(exc),
                }
            )
            continue
        parent_documents.append(document)

    valid_text_documents: list[JsonObject] = []
    for record in text_records:
        try:
            document = to_document(record, "bill_text", preserve_raw=preserve_raw)
            validate_document(document, "bill_text")
        except (TypeError, ValueError) as exc:
            quarantine.append(
                {
                    "resource": "bill_text",
                    "id": str(record.get("id", "")),
                    "reason": str(exc),
                }
            )
            continue
        valid_text_documents.append(document)

    parent_write = None
    text_write = None
    if not preview:
        if client is None or target_index is None:
            raise ValueError(
                "Staging writes require a search client and explicit target"
            )
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
        "archives_read": archives_read,
        "parent_input_count": len(parent_records),
        "parent_count": len(parent_documents),
        "reconciled_parent_count": len(reconciliation.records),
        "text_version_count": len(valid_text_documents),
        "document_count": len(parent_documents) + len(valid_text_documents),
        "quarantine_count": len(quarantine),
        "quarantine": quarantine,
        "diagnostics": [
            item.model_dump(mode="json") for item in reconciliation.diagnostics
        ],
        "write": write_result,
        "target_inventory": inventory.model_dump(mode="json")
        if inventory is not None
        else None,
        "target_inventory_unavailable_reason": "Archive-only preview; no serving-target inventory was requested."
        if inventory is None
        else None,
        "archive_fields": sorted({key for record in parent_records for key in record}),
        "sample_limit": max_records,
        "audited": len(parent_documents) + len(valid_text_documents),
        "status": "preview" if preview else "completed",
        "source_coverage": "partial",
        "promotable": False,
        "coverage": [
            ResourceCoverage(
                resource=resource,
                congress=next(iter(congresses))
                if resource == "bill" and len(congresses) == 1
                else None,
                checked_at=checked_at if resource == "bill" else None,
                discovery=StageCoverage(
                    observed=count,
                    reason="Selected archives are not an authoritative upstream inventory.",
                ),
                hydration=StageCoverage(
                    observed=valid,
                    failed=any(item["resource"] == resource for item in quarantine),
                    reason="Retained-record validation is archive-scoped; any rejected records are listed in quarantine.",
                ),
                indexing=StageCoverage(
                    observed=0 if preview else valid,
                    reason="Index acceptance is scoped to selected archives, not source coverage.",
                ),
                assessed_at=datetime.now(UTC),
            ).model_dump(mode="json")
            for resource, count, valid in (
                ("bill", len(parent_records), len(parent_documents)),
                ("bill_text", len(text_records), len(valid_text_documents)),
            )
        ],
        "required_coverage": [
            ResourceCoverage(
                resource=config.resource.value,
                congress=congress,
                scope="required_history",
                discovery=StageCoverage(
                    unavailable=True,
                    reason="Selected archives do not establish upstream support or full discovery for this scope.",
                ),
                hydration=StageCoverage(
                    unavailable=True,
                    reason="No complete hydration inventory for this scope.",
                ),
                indexing=StageCoverage(
                    unavailable=True,
                    reason="No identity-level comparison with the serving projection for this scope.",
                ),
                assessed_at=datetime.now(UTC),
            ).model_dump(mode="json")
            for config in RESOURCE_CONFIGS.values()
            for congress in (
                [None]
                if config.scope == "static"
                else range(
                    history.first_congress,
                    history.last_congress + 1,
                )
            )
        ],
    }
    validated = ReplayReport.model_validate(report)
    for assessment in validated.coverage:
        if assessment.congress == history.last_congress:
            assessment.assess_freshness(SourcePolicy())
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(validated.model_dump_json(indent=2) + "\n")
    return validated.model_dump(mode="json")

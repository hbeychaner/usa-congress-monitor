"""Explicit bounded source repair; graph pointer publication is never performed."""

from __future__ import annotations

import fcntl
import os
from collections.abc import Iterator
from copy import deepcopy
from datetime import UTC, datetime
from enum import StrEnum
from itertools import batched
from pathlib import Path
from typing import Literal
from uuid import uuid4

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from pydantic import AliasPath, AwareDatetime, BaseModel, ConfigDict, Field

from cdm.config.topic_analysis import GraphRepairMappingField
from cdm.graph.models import (
    GraphIndexDefinition,
    GraphMapping,
    GraphVersionPointer,
    MappingField,
    Signal,
)
from cdm.graph.repair import (
    BundleFile,
    ClusterIdentity,
    FileSeal,
    GraphRepairCapture,
    GraphRepairRehearsal,
    IndexRole,
    RecordId,
    RehearsalReport,
    RepairBundle,
    RepairMaterial,
    SourceState,
    StoredDocument,
)
from cdm.store.index_manager import load_definitions
from cdm.utils.json_types import JsonObject


class ClusterStatus(StrEnum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class RepairHealth(BaseModel):
    status: ClusterStatus
    timed_out: bool
    unassigned_primary_shards: int = Field(ge=0)
    initializing_shards: int = Field(ge=0)
    relocating_shards: int = Field(ge=0)
    number_of_data_nodes: int = Field(gt=0)

    def require_ready(self) -> None:
        if (
            self.status is ClusterStatus.RED
            or self.timed_out
            or self.unassigned_primary_shards
            or self.initializing_shards
            or self.relocating_shards
        ):
            raise ValueError("Cluster is not ready for bounded repair")


class DocumentCount(BaseModel):
    count: int = Field(ge=0)
    failed_shards: int = Field(validation_alias=AliasPath("_shards", "failed"), ge=0)

    @classmethod
    def read(
        cls, client: Elasticsearch, index: str, query: JsonObject | None = None
    ) -> int:
        result = cls.model_validate(client.count(index=index, query=query).body)
        if result.failed_shards:
            raise ValueError("Incomplete document count")
        return result.count


class DocumentBatch(BaseModel):
    docs: list[StoredDocument]


class RepairPlan(BaseModel):
    schema_version: Literal[1] = 1
    prepared_at: AwareDatetime
    bundle_manifest: FileSeal
    graph_backup: FileSeal
    graph_records: int = Field(gt=0)
    mapping_patch: GraphMapping
    mapping_paths: list[GraphRepairMappingField]
    rehearsal: RehearsalReport
    restore_cluster: ClusterIdentity
    health: RepairHealth


class RepairStart(BaseModel):
    started_at: AwareDatetime
    plan: FileSeal


class RepairReceipt(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: RecordId = Field(validation_alias="_id")
    seq_no: int = Field(validation_alias="_seq_no", ge=0)
    primary_term: int = Field(validation_alias="_primary_term", gt=0)


class RepairAction(StrEnum):
    APPLY = "apply"
    ROLLBACK = "rollback"


class RepairResult(BaseModel):
    schema_version: Literal[1] = 1
    action: RepairAction
    finished_at: AwareDatetime
    plan: FileSeal
    receipts: FileSeal
    records: int = Field(ge=0)
    source_records: int = Field(gt=0)
    graph_records: int = Field(gt=0)
    mapping_paths: list[GraphRepairMappingField]
    health: RepairHealth
    pointers_unchanged: Literal[True] = True


class AppliedRepair(BaseModel):
    material: RepairMaterial
    plan: RepairPlan
    report: RepairResult
    report_seal: FileSeal


class GraphBackup:
    """Streams bounded backups and checks exact sources through real-time multi-get."""

    def __init__(
        self,
        client: Elasticsearch,
        bundle: RepairBundle,
        count: int,
        name: BundleFile = BundleFile.GRAPH_BACKUP,
    ) -> None:
        self.client = client
        self.bundle = bundle
        self.count = count
        self.name = name

    def verify(
        self,
        index: str,
        *,
        versions: bool,
        extra_records: int = 0,
        voting_pointer: StoredDocument | None = None,
    ) -> None:
        if (
            extra_records < 0
            or voting_pointer is not None
            and voting_pointer.id != GraphVersionPointer.pointer_id(Signal.VOTING)
        ):
            raise ValueError("Invalid graph preservation scope")
        seen: set[RecordId] = set()
        for batch in batched(self.bundle.rows(self.name, StoredDocument), 500):
            expected = {doc.id: doc for doc in batch}
            if voting_pointer is not None and voting_pointer.id in expected:
                expected[voting_pointer.id] = voting_pointer
            response = DocumentBatch.model_validate(
                self.client.mget(index=index, ids=list(expected)).body
            ).docs
            actual = {doc.id: doc for doc in response}
            if (
                len(expected) != len(batch)
                or len(actual) != len(response)
                or seen.intersection(expected)
                or (
                    actual != expected
                    if versions
                    else {key: doc.source for key, doc in actual.items()}
                    != {key: doc.source for key, doc in expected.items()}
                )
            ):
                raise ValueError("Graph backup content/version verification failed")
            seen.update(expected)
        if (
            len(seen) != self.count
            or DocumentCount.read(self.client, index) != self.count + extra_records
        ):
            raise ValueError("Graph backup identity/count verification failed")

    def restore(self, state: SourceState) -> ClusterIdentity:
        cluster = ClusterIdentity.model_validate(self.client.info().body)
        if cluster == state.cluster:
            raise ValueError("Backup restore must use a different cluster UUID")
        nonce = uuid4().hex
        index = f"graph-repair-restore-{nonce}"
        mapping = deepcopy(state.indices[IndexRole.GRAPH].mappings)
        mapping["_meta"] = {"graph_rehearsal_owner": nonce}
        self.client.indices.create(
            index=index,
            mappings=mapping,
            settings={"number_of_shards": 1, "number_of_replicas": 0},
        )
        try:
            bulk(
                self.client,
                (
                    {
                        "_op_type": "index",
                        "_index": index,
                        "_id": doc.id,
                        "_source": doc.source,
                    }
                    for doc in self.bundle.rows(BundleFile.GRAPH_BACKUP, StoredDocument)
                ),
                raise_on_error=True,
                raise_on_exception=True,
            )
            self.client.indices.refresh(index=index)
            self.verify(index, versions=False)
        finally:
            metadata = self.client.indices.get_mapping(index=index)[index]["mappings"]
            if metadata.get("_meta", {}).get("graph_rehearsal_owner") != nonce:
                raise ValueError("Refusing cleanup of non-owned graph restore index")
            self.client.indices.delete(index=index)
        return cluster


class LiveGraphRepair:
    def __init__(
        self,
        capture: GraphRepairCapture,
        rehearsal: GraphRepairRehearsal | None = None,
    ) -> None:
        self.capture = capture
        self.client = capture.client
        self.rehearsal = rehearsal

    def _health(self) -> RepairHealth:
        health = RepairHealth.model_validate(
            self.client.cluster.health(timeout="10s").body
        )
        health.require_ready()
        return health

    def require_applied(
        self,
        root: Path,
        output: Path,
        *,
        voting_pointer: StoredDocument | None = None,
    ) -> AppliedRepair:
        material, plan, seal = self._load(root, output)
        report_seal = FileSeal.read(output / BundleFile.APPLIED)
        report = RepairResult.model_validate_json(
            (output / BundleFile.APPLIED).read_text()
        )
        receipts = self._receipts(output / BundleFile.JOURNAL)
        if (
            report.plan != seal
            or report.receipts != FileSeal.read(output / BundleFile.JOURNAL)
            or report.action is not RepairAction.APPLY
            or report.records != len(material.repairs)
            or set(receipts) != set(material.repairs)
            or report.source_records != len(material.originals)
            or report.graph_records != plan.graph_records
        ):
            raise ValueError("Completed source repair evidence is inconsistent")
        expected = dict(material.originals)
        for identity, receipt in receipts.items():
            expected[identity] = material.repairs[identity].model_copy(
                update={
                    "seq_no": receipt.seq_no,
                    "primary_term": receipt.primary_term,
                }
            )
        checked = material.model_copy(
            update={"state": material.state.model_copy(deep=True)}
        )
        if voting_pointer is not None:
            if voting_pointer.id != GraphVersionPointer.pointer_id(Signal.VOTING):
                raise ValueError("Only a voting pointer replacement is permitted")
            checked.state.pointers[Signal.VOTING] = voting_pointer
        self._health()
        self._require_state(checked, plan.mapping_patch)
        if self._source(material) != expected:
            raise ValueError("Repaired source versions/content changed")
        return AppliedRepair(
            material=material, plan=plan, report=report, report_seal=report_seal
        )

    @staticmethod
    def _patch(expected: GraphMapping, actual: GraphMapping) -> GraphMapping:
        properties: dict[MappingField, GraphMapping] = {}
        for name, field in expected.properties.items():
            if name not in actual.properties:
                properties[name] = field
            else:
                child = LiveGraphRepair._patch(field, actual.properties[name])
                if child.properties:
                    properties[name] = child.model_copy(update={"type": field.type})
        return GraphMapping(properties=properties)

    def _mapping_plan(self, material: RepairMaterial) -> GraphMapping:
        expected = GraphIndexDefinition.model_validate(
            load_definitions()["analysis_graph"]
        ).mappings
        actual = GraphMapping.model_validate(
            material.state.indices[IndexRole.GRAPH].mappings
        )
        differences = expected.differences(actual)
        paths = {f"{field}: missing mapping" for field in GraphRepairMappingField}
        if set(differences) != paths:
            raise ValueError(
                "Mapping drift is not exactly the eight approved additions"
            )
        return self._patch(expected, actual)

    def _source(self, material: RepairMaterial) -> dict[RecordId, StoredDocument]:
        return RepairBundle.unique(
            GraphRepairCapture.read_documents(
                self.client,
                material.state.indices[IndexRole.SOURCE].name,
                {
                    "range": {
                        "congress": {"gte": material.manifest.config.first_congress}
                    }
                },
            ),
            material.manifest.config.max_source_records,
        )

    def _require_state(
        self, material: RepairMaterial, patch: GraphMapping | None = None
    ) -> None:
        expected = material.state.model_copy(deep=True)
        if patch is not None:
            expected_mapping = deepcopy(expected.indices[IndexRole.GRAPH].mappings)
            self._merge(
                expected_mapping, patch.model_dump(mode="json", exclude_defaults=True)
            )
            expected.indices[IndexRole.GRAPH].mappings = expected_mapping
        if self.capture._state() != expected:
            raise ValueError(
                "Cluster, topology, mapping or pointer preconditions changed"
            )

    @staticmethod
    def _merge(target: JsonObject, patch: JsonObject) -> None:
        for key, value in patch.items():
            existing = target.get(key)
            if isinstance(value, dict) and isinstance(existing, dict):
                LiveGraphRepair._merge(existing, value)
            else:
                target[key] = value

    def prepare(self, root: Path, accepted: Path, output: Path) -> RepairPlan:
        if self.rehearsal is None:
            raise ValueError("Preparation requires an isolated backup restore client")
        bundle = RepairBundle(root)
        material = bundle.material()
        manifest_seal = FileSeal.read(root / BundleFile.MANIFEST)
        FileSeal.read(accepted / BundleFile.REPORT)
        report = RehearsalReport.model_validate_json(
            (accepted / BundleFile.REPORT).read_text()
        )
        if (
            report.bundle_manifest != manifest_seal
            or report.bundle_id != material.manifest.bundle_id
            or report.source_cluster_uuid != material.state.cluster.cluster_uuid
            or report.source_records != len(material.originals)
            or report.repaired_records != len(material.repairs)
            or report.edge_count <= 0
            or report.congress_114_edges <= 0
            or len(report.candidate_files) != 2
            or {seal.name for seal in report.candidate_files}
            != {BundleFile.EDGES, BundleFile.POINTER}
        ):
            raise ValueError("Rehearsal is not bound to the approved source bundle")
        for seal in report.candidate_files:
            if FileSeal.read(accepted / seal.name) != seal:
                raise ValueError("Accepted candidate checksum mismatch")
        health = self._health()
        self._require_state(material)
        if self._source(material) != material.originals:
            raise ValueError("Captured source versions/content changed")
        patch = self._mapping_plan(material)
        count = DocumentCount.read(
            self.client, material.state.indices[IndexRole.GRAPH].name
        )
        if not 0 < count <= material.manifest.config.max_graph_records:
            raise ValueError(
                "Graph backup exceeds the approved record bound or is empty"
            )
        result = RepairBundle(output)
        result.create()
        written = result.write_rows(BundleFile.GRAPH_BACKUP, self._graph_rows(material))
        if written != count:
            raise ValueError("Graph changed during backup capture")
        graph_seal = FileSeal.read(output / BundleFile.GRAPH_BACKUP)
        GraphBackup(self.client, result, count).verify(
            material.state.indices[IndexRole.GRAPH].name, versions=True
        )
        restore_cluster = GraphBackup(self.rehearsal.client, result, count).restore(
            material.state
        )
        self._require_state(material)
        if self._source(material) != material.originals:
            raise ValueError("Source changed during backup restore proof")
        bundle.verify()
        if FileSeal.read(root / BundleFile.MANIFEST) != manifest_seal:
            raise ValueError("Input manifest changed during backup preparation")
        if FileSeal.read(output / BundleFile.GRAPH_BACKUP) != graph_seal:
            raise ValueError("Graph backup changed during restore proof")
        plan = RepairPlan(
            prepared_at=datetime.now(UTC),
            bundle_manifest=manifest_seal,
            graph_backup=graph_seal,
            graph_records=count,
            mapping_patch=patch,
            mapping_paths=list(GraphRepairMappingField),
            rehearsal=report,
            restore_cluster=restore_cluster,
            health=health,
        )
        result.write(BundleFile.PREPARED, plan)
        return plan

    def _graph_rows(self, material: RepairMaterial) -> Iterator[StoredDocument]:
        seen: set[RecordId] = set()
        for row in GraphRepairCapture.read_documents(
            self.client,
            material.state.indices[IndexRole.GRAPH].name,
            {"match_all": {}},
        ):
            if row.id in seen:
                raise ValueError("Duplicate or inconsistent graph backup identity")
            seen.add(row.id)
            if len(seen) > material.manifest.config.max_graph_records:
                raise ValueError("Graph backup exceeds the approved record bound")
            yield row

    def _load(
        self, root: Path, output: Path
    ) -> tuple[RepairMaterial, RepairPlan, FileSeal]:
        if output.is_symlink():
            raise ValueError("Prepared evidence directory must not be a symlink")
        material = RepairBundle(root).material()
        seal = FileSeal.read(output / BundleFile.PREPARED)
        plan = RepairPlan.model_validate_json(
            (output / BundleFile.PREPARED).read_text()
        )
        if (
            plan.bundle_manifest != FileSeal.read(root / BundleFile.MANIFEST)
            or plan.graph_backup != FileSeal.read(output / BundleFile.GRAPH_BACKUP)
            or plan.mapping_patch != self._mapping_plan(material)
            or plan.mapping_paths != list(GraphRepairMappingField)
            or plan.restore_cluster == material.state.cluster
        ):
            raise ValueError("Prepared repair evidence changed or is not approved")
        return material, plan, seal

    def apply(self, root: Path, output: Path) -> RepairResult:
        material, plan, seal = self._load(root, output)
        self._health()
        self._require_state(material)
        if self._source(material) != material.originals:
            raise ValueError("Source preconditions changed; refusing all writes")
        GraphBackup(self.client, RepairBundle(output), plan.graph_records).verify(
            material.state.indices[IndexRole.GRAPH].name,
            versions=True,
        )
        result = RepairBundle(output)
        result.write(
            BundleFile.STARTED, RepairStart(started_at=datetime.now(UTC), plan=seal)
        )
        with (output / BundleFile.JOURNAL).open("x", encoding="utf-8") as journal:
            response = self.client.indices.put_mapping(
                index=material.state.indices[IndexRole.GRAPH].name,
                **plan.mapping_patch.model_dump(mode="json", exclude_defaults=True),
            )
            if response["acknowledged"] is not True:
                raise ValueError(
                    "Mapping acknowledgement indeterminate; inspect before retry"
                )
            self._require_state(material, plan.mapping_patch)
            for identity, after in material.repairs.items():
                before = material.originals[identity]
                receipt = RepairReceipt.model_validate(
                    self.client.index(
                        index=material.state.indices[IndexRole.SOURCE].name,
                        id=identity,
                        document=after.source,
                        if_seq_no=before.seq_no,
                        if_primary_term=before.primary_term,
                    ).body
                )
                if receipt.id != identity:
                    raise ValueError(
                        "Write response identity mismatch; inspect before retry"
                    )
                journal.write(receipt.model_dump_json(by_alias=False) + "\n")
                journal.flush()
                os.fsync(journal.fileno())
        return self._finish(root, material, plan, seal, output, rollback=False)

    def rollback(self, root: Path, output: Path) -> RepairResult:
        material, plan, seal = self._load(root, output)
        FileSeal.read(output / BundleFile.STARTED)
        start = RepairStart.model_validate_json(
            (output / BundleFile.STARTED).read_text()
        )
        if start.plan != seal:
            raise ValueError("Repair plan changed after application started")
        self._health()
        self._require_state(material, plan.mapping_patch)
        receipts = self._receipts(output / BundleFile.JOURNAL)
        completed = output / BundleFile.APPLIED
        if completed.exists():
            FileSeal.read(completed)
            report = RepairResult.model_validate_json(completed.read_text())
            if report.plan != seal or report.receipts != FileSeal.read(
                output / BundleFile.JOURNAL
            ):
                raise ValueError("Completed repair receipts changed")
        rollback_path = output / BundleFile.ROLLBACK_JOURNAL
        if rollback_path.exists() or rollback_path.is_symlink():
            FileSeal.read(rollback_path)
        with rollback_path.open("a+", encoding="utf-8") as journal:
            fcntl.flock(journal.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            restored_receipts = self._receipts(rollback_path)
            if not set(restored_receipts).issubset(receipts):
                raise ValueError("Unexpected identity in rollback receipt")
            self.client.indices.refresh(
                index=material.state.indices[IndexRole.SOURCE].name
            )
            expected = dict(material.originals)
            for identity, receipt in receipts.items():
                if identity not in material.repairs:
                    raise ValueError("Unexpected identity in repair receipt")
                version = restored_receipts.get(identity, receipt)
                document = (
                    material.originals[identity]
                    if identity in restored_receipts
                    else material.repairs[identity]
                )
                expected[identity] = document.model_copy(
                    update={
                        "seq_no": version.seq_no,
                        "primary_term": version.primary_term,
                    }
                )
            if self._source(material) != expected:
                raise ValueError(
                    "Concurrent/indeterminate source write; refusing rollback"
                )
            for identity, receipt in receipts.items():
                if identity in restored_receipts:
                    continue
                restored = RepairReceipt.model_validate(
                    self.client.index(
                        index=material.state.indices[IndexRole.SOURCE].name,
                        id=identity,
                        document=material.originals[identity].source,
                        if_seq_no=receipt.seq_no,
                        if_primary_term=receipt.primary_term,
                    ).body
                )
                if restored.id != identity:
                    raise ValueError("Rollback response identity mismatch")
                journal.write(restored.model_dump_json(by_alias=False) + "\n")
                journal.flush()
                os.fsync(journal.fileno())
        return self._finish(root, material, plan, seal, output, rollback=True)

    @staticmethod
    def _receipts(path: Path) -> dict[RecordId, RepairReceipt]:
        FileSeal.read(path)
        receipts: dict[RecordId, RepairReceipt] = {}
        for line in path.read_text().splitlines():
            receipt = RepairReceipt.model_validate_json(line)
            if receipt.id in receipts:
                raise ValueError("Duplicate repair receipt")
            receipts[receipt.id] = receipt
        return receipts

    def _finish(
        self,
        root: Path,
        material: RepairMaterial,
        plan: RepairPlan,
        seal: FileSeal,
        output: Path,
        *,
        rollback: bool,
    ) -> RepairResult:
        self.client.indices.refresh(index=material.state.indices[IndexRole.SOURCE].name)
        self._require_state(material, plan.mapping_patch)
        current = self._source(material)
        expected = (
            material.originals if rollback else material.originals | material.repairs
        )
        if {key: doc.source for key, doc in current.items()} != {
            key: doc.source for key, doc in expected.items()
        }:
            raise ValueError("Complete source content verification failed")
        name = BundleFile.ROLLBACK_JOURNAL if rollback else BundleFile.JOURNAL
        receipts = self._receipts(output / name)
        for identity, receipt in receipts.items():
            actual = current[identity]
            if (
                actual.seq_no != receipt.seq_no
                or actual.primary_term != receipt.primary_term
            ):
                raise ValueError("Post-write version verification failed")
        if any(
            current[key] != doc
            for key, doc in material.originals.items()
            if key not in receipts
        ):
            raise ValueError("Unrelated source versions changed")
        if not rollback and set(receipts) != set(material.repairs):
            raise ValueError("Repair receipt identity set is incomplete")
        if rollback and set(receipts) != set(
            self._receipts(output / BundleFile.JOURNAL)
        ):
            raise ValueError("Rollback receipt identity set is incomplete")
        GraphBackup(self.client, RepairBundle(output), plan.graph_records).verify(
            material.state.indices[IndexRole.GRAPH].name,
            versions=True,
        )
        RepairBundle(root).verify()
        if (
            FileSeal.read(output / BundleFile.PREPARED) != seal
            or FileSeal.read(root / BundleFile.MANIFEST) != plan.bundle_manifest
            or FileSeal.read(output / BundleFile.GRAPH_BACKUP) != plan.graph_backup
        ):
            raise ValueError("Prepared repair plan changed during operation")
        report = RepairResult(
            action=RepairAction.ROLLBACK if rollback else RepairAction.APPLY,
            finished_at=datetime.now(UTC),
            plan=seal,
            receipts=FileSeal.read(output / name),
            records=len(receipts),
            source_records=len(current),
            graph_records=plan.graph_records,
            mapping_paths=plan.mapping_paths,
            health=self._health(),
            pointers_unchanged=True,
        )
        RepairBundle(output).write(
            BundleFile.ROLLED_BACK if rollback else BundleFile.APPLIED, report
        )
        return report

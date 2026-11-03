"""Sealed read-only vote repair captures and isolated graph/rollback rehearsals."""

from __future__ import annotations

import hashlib
import math
import os
import shutil
from collections.abc import Iterable, Iterator
from copy import deepcopy
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal, NewType
from uuid import uuid4

from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch.helpers import bulk, scan
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from cdm.config.source_policy import FieldName
from cdm.config.topic_analysis import (
    GraphRepairConfig,
    GraphStoreConfig,
    VoteRepairField,
)
from cdm.graph.job import GraphBuildJob
from cdm.graph.models import GraphVersionPointer, MemberEdge, Signal
from cdm.graph.store import BillSignatureReader, GraphStore, RollCallReader
from cdm.graph.topics import TopicModelReader
from cdm.ingest.voteview import Chamber, CsvFile, CsvKind, RollCallBuilder
from cdm.store.client import SearchCompletion
from cdm.store.index_manager import load_definitions
from cdm.store.opensearch import index_name, read_alias
from cdm.utils.json_types import JsonObject, JsonValue

RecordId = NewType("RecordId", str)


class BundleFile(StrEnum):
    MANIFEST = "manifest.json"
    STATE = "state.json"
    SOURCE = "source.jsonl"
    REPAIRS = "repairs.jsonl"
    DIFFS = "diffs.jsonl"
    EDGES = "candidate-edges.jsonl"
    POINTER = "candidate-pointer.json"
    REPORT = "acceptance.json"
    GRAPH_BACKUP = "graph-before.jsonl"
    PREPARED = "repair-plan.json"
    STARTED = "repair-started.json"
    JOURNAL = "repair-receipts.jsonl"
    APPLIED = "repair-applied.json"
    ROLLBACK_JOURNAL = "rollback-receipts.jsonl"
    ROLLED_BACK = "repair-rolled-back.json"
    PROMOTION_PLAN = "voting-promotion-plan.json"
    STAGED_DOCUMENTS = "voting-staged-documents.jsonl"
    STAGED = "voting-staged.json"
    SERVING_ACCEPTANCE = "voting-serving-acceptance.json"
    SERVING_BROWSER = "browser-before.json"
    PROMOTION_STARTED = "voting-promotion-started.json"
    PROMOTION_RECEIPT = "voting-promotion-receipt.json"
    PROMOTED = "voting-promoted.json"
    POINTER_ROLLBACK_STARTED = "voting-rollback-started.json"
    POINTER_ROLLBACK_RECEIPT = "voting-rollback-receipt.json"
    POINTER_ROLLED_BACK = "voting-rolled-back.json"


class IndexRole(StrEnum):
    SOURCE = "source"
    GRAPH = "graph"


class StoredDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: RecordId = Field(validation_alias="_id", min_length=1)
    source: JsonObject = Field(validation_alias="_source")
    seq_no: int = Field(validation_alias="_seq_no", ge=0)
    primary_term: int = Field(validation_alias="_primary_term", gt=0)


class IndexImage(BaseModel):
    name: str
    aliases: JsonObject
    mappings: JsonObject
    settings: JsonObject


class ClusterIdentity(BaseModel):
    cluster_uuid: str = Field(min_length=1)

    @field_validator("cluster_uuid")
    @classmethod
    def require_stable_cluster(cls, value: str) -> str:
        if value == "_na_":
            raise ValueError("A stable cluster UUID is required")
        return value


class SourceState(BaseModel):
    cluster: ClusterIdentity
    indices: dict[IndexRole, IndexImage]
    pointers: dict[Signal, StoredDocument | None]


class FileSeal(BaseModel):
    name: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size: int = Field(ge=0)

    @field_validator("name")
    @classmethod
    def require_basename(cls, value: str) -> str:
        if value in ("", ".", "..") or Path(value).name != value or "\\" in value:
            raise ValueError("Bundle files must be plain basenames")
        return value

    @classmethod
    def read(cls, path: Path) -> FileSeal:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Missing or unsafe evidence file: {path}")
        with path.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        return cls(name=path.name, sha256=digest, size=path.stat().st_size)


class RepairManifest(BaseModel):
    schema_version: Literal[1] = 1
    mode: Literal["read_only_capture"] = "read_only_capture"
    bundle_id: str
    captured_at: AwareDatetime
    config: GraphRepairConfig
    source_records: int = Field(gt=0)
    repair_records: int = Field(gt=0)
    files: list[FileSeal]


class FieldChange(BaseModel):
    field: FieldName
    before_present: bool
    before: JsonValue
    after: JsonValue


class RepairDiff(BaseModel):
    id: RecordId
    changes: list[FieldChange]


class RepairIdentity(BaseModel):
    id: RecordId
    congress: int
    chamber: Chamber
    roll_number: int


class RehearsalReport(BaseModel):
    schema_version: Literal[1] = 1
    mode: Literal["isolated_rehearsal"] = "isolated_rehearsal"
    bundle_id: str
    bundle_manifest: FileSeal
    source_cluster_uuid: str
    staging_cluster_uuid: str
    source_records: int
    repaired_records: int
    graph_version: str
    edge_count: int
    congresses: list[int]
    congress_114_edges: int
    rollback_verified: Literal[True] = True
    live_writes_performed: Literal[False] = False
    candidate_files: list[FileSeal]


class RepairMaterial(BaseModel):
    manifest: RepairManifest
    state: SourceState
    originals: dict[RecordId, StoredDocument]
    repairs: dict[RecordId, StoredDocument]


class RepairBundle:
    """Local immutable inputs; a final manifest is written only after capture succeeds."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def create(self) -> None:
        self.root.mkdir(parents=True, mode=0o700, exist_ok=False)

    def write(self, name: BundleFile, value: BaseModel) -> None:
        with (self.root / name).open("x", encoding="utf-8") as handle:
            handle.write(value.model_dump_json(indent=2))
            handle.flush()
            os.fsync(handle.fileno())

    def rows[T: BaseModel](self, name: BundleFile, model: type[T]) -> Iterator[T]:
        with (self.root / name).open(encoding="utf-8") as handle:
            for line in handle:
                yield model.model_validate_json(line)

    def write_rows(self, name: BundleFile, rows: Iterable[BaseModel]) -> int:
        count = 0
        with (self.root / name).open("x", encoding="utf-8") as handle:
            for row in rows:
                handle.write(row.model_dump_json() + "\n")
                count += 1
            handle.flush()
            os.fsync(handle.fileno())
        return count

    def verify(self) -> RepairManifest:
        if self.root.is_symlink():
            raise ValueError("Evidence directory must not be a symlink")
        FileSeal.read(self.root / BundleFile.MANIFEST)
        manifest = RepairManifest.model_validate_json(
            (self.root / BundleFile.MANIFEST).read_text()
        )
        names = [seal.name for seal in manifest.files]
        required: set[str] = {
            BundleFile.STATE,
            BundleFile.SOURCE,
            BundleFile.REPAIRS,
            BundleFile.DIFFS,
        }
        required.update(
            CsvFile(kind=kind, chamber=chamber, congress=manifest.config.congress).name
            for chamber in Chamber
            for kind in CsvKind
        )
        if len(set(names)) != len(names) or set(names) != required:
            raise ValueError("Incomplete or duplicate evidence manifest")
        if {path.name for path in self.root.iterdir()} != required | {
            BundleFile.MANIFEST
        }:
            raise ValueError("Unexpected files in sealed evidence directory")
        for expected in manifest.files:
            if FileSeal.read(self.root / expected.name) != expected:
                raise ValueError(f"Evidence checksum mismatch: {expected.name}")
        return manifest

    def state(self) -> SourceState:
        return SourceState.model_validate_json(
            (self.root / BundleFile.STATE).read_text()
        )

    def material(self) -> RepairMaterial:
        manifest = self.verify()
        originals = self.unique(
            self.rows(BundleFile.SOURCE, StoredDocument),
            manifest.config.max_source_records,
        )
        repairs, diffs = GraphRepairCapture.compare(self, originals, manifest.config)
        if (
            repairs != self.unique(self.rows(BundleFile.REPAIRS, StoredDocument))
            or diffs != list(self.rows(BundleFile.DIFFS, RepairDiff))
            or len(originals) != manifest.source_records
            or len(repairs) != manifest.repair_records
        ):
            raise ValueError(
                "Sealed repair derivation/counts do not match frozen evidence"
            )
        return RepairMaterial(
            manifest=manifest, state=self.state(), originals=originals, repairs=repairs
        )

    @staticmethod
    def unique(
        rows: Iterable[StoredDocument], limit: int | None = None
    ) -> dict[RecordId, StoredDocument]:
        documents: dict[RecordId, StoredDocument] = {}
        for row in rows:
            if row.id in documents or row.source.get("id") != row.id:
                raise ValueError(
                    f"Duplicate or inconsistent document identity: {row.id}"
                )
            documents[row.id] = row
            if limit is not None and len(documents) > limit:
                raise ValueError("Source scope exceeds the approved capture bound")
        return documents


class GraphRepairCapture:
    """Reads the serving cluster and retained CSVs; has no store-writing operation."""

    def __init__(
        self,
        client: Elasticsearch,
        config: GraphRepairConfig,
        *,
        source_index: str | None = None,
        graph_index: str | None = None,
    ) -> None:
        self.client = client
        self.config = config
        self.source_index = source_index or read_alias("rollcall")
        self.graph_index = graph_index or index_name("analysis_graph")

    def _index_image(self, target: str) -> IndexImage:
        response = self.client.indices.get(index=target).body
        if len(response) != 1:
            raise ValueError(f"Capture requires exactly one physical index: {target}")
        name, definition = next(iter(response.items()))
        return IndexImage.model_validate({"name": name, **definition})

    def _state(self) -> SourceState:
        indices = {
            IndexRole.SOURCE: self._index_image(self.source_index),
            IndexRole.GRAPH: self._index_image(self.graph_index),
        }
        pointers: dict[Signal, StoredDocument | None] = {}
        for signal in Signal:
            try:
                response = self.client.get(
                    index=indices[IndexRole.GRAPH].name,
                    id=GraphVersionPointer.pointer_id(signal),
                )
            except NotFoundError:
                pointers[signal] = None
            else:
                pointers[signal] = StoredDocument.model_validate(response.body)
        return SourceState(
            cluster=ClusterIdentity.model_validate(self.client.info().body),
            indices=indices,
            pointers=pointers,
        )

    @staticmethod
    def read_documents(
        client: Elasticsearch,
        index: str,
        query: JsonObject,
    ) -> Iterator[StoredDocument]:
        for hit in scan(
            client,
            index=index,
            query={"query": query},
            seq_no_primary_term=True,
            allow_partial_search_results=False,
        ):
            yield StoredDocument.model_validate(hit)

    def capture(self, output: Path) -> RepairManifest:
        bundle = RepairBundle(output)
        bundle.create()
        for chamber in Chamber:
            for kind in CsvKind:
                name = CsvFile(
                    kind=kind, chamber=chamber, congress=self.config.congress
                ).name
                source = self.config.cache_dir / name
                expected = FileSeal.read(source)
                shutil.copyfile(source, output / name)
                if (
                    FileSeal.read(source) != expected
                    or FileSeal.read(output / name) != expected
                ):
                    raise ValueError(f"CSV changed during capture: {name}")
        state = self._state()
        bundle.write(BundleFile.STATE, state)
        query: JsonObject = {"range": {"congress": {"gte": self.config.first_congress}}}
        documents = RepairBundle.unique(
            self.read_documents(
                self.client,
                state.indices[IndexRole.SOURCE].name,
                query,
            ),
            self.config.max_source_records,
        )
        if not documents or len(documents) > self.config.max_source_records:
            raise ValueError(
                "Source scope is empty or exceeds the approved capture bound"
            )
        bundle.write_rows(BundleFile.SOURCE, documents.values())
        repairs, diffs = self.compare(bundle, documents, self.config)
        bundle.write_rows(BundleFile.REPAIRS, repairs.values())
        bundle.write_rows(BundleFile.DIFFS, diffs)
        if self._state() != state:
            raise ValueError("Index topology or graph pointers changed during capture")
        manifest = RepairManifest(
            bundle_id=uuid4().hex,
            captured_at=datetime.now(UTC),
            config=self.config,
            source_records=len(documents),
            repair_records=len(repairs),
            files=sorted(
                (FileSeal.read(path) for path in output.iterdir()),
                key=lambda seal: seal.name,
            ),
        )
        bundle.write(BundleFile.MANIFEST, manifest)
        bundle.verify()
        return manifest

    @staticmethod
    def compare(
        bundle: RepairBundle,
        documents: dict[RecordId, StoredDocument],
        config: GraphRepairConfig,
    ) -> tuple[dict[RecordId, StoredDocument], list[RepairDiff]]:
        originals = {
            identity: document
            for identity, document in documents.items()
            if RepairIdentity.model_validate(document.source).congress
            == config.congress
        }
        repairs: dict[RecordId, StoredDocument] = {}
        diffs: list[RepairDiff] = []
        for chamber in Chamber:
            paths = {
                kind: bundle.root
                / CsvFile(kind=kind, chamber=chamber, congress=config.congress).name
                for kind in CsvKind
            }
            records = list(
                RollCallBuilder(
                    paths[CsvKind.MEMBERS],
                    paths[CsvKind.ROLLCALLS],
                    paths[CsvKind.VOTES],
                ).build()
            )
            expected = (
                config.expected_house
                if chamber is Chamber.HOUSE
                else config.expected_senate
            )
            if len(records) != expected:
                raise ValueError(
                    f"Unexpected {chamber} repair count: {len(records)} != {expected}"
                )
            for record in records:
                identity = RecordId(record.id)
                if (
                    identity not in originals
                    or identity in repairs
                    or record.congress != config.congress
                    or record.chamber is not chamber
                ):
                    raise ValueError(
                        f"Unexpected or duplicate repair identity: {identity}"
                    )
                before = originals[identity]
                candidate = dict(before.source)
                changes: list[FieldChange] = []
                for field, value in record.to_index_document().items():
                    if field not in set(VoteRepairField):
                        if before.source.get(field) != value:
                            raise ValueError(
                                f"Unexplained metadata difference: {identity} {field}"
                            )
                    elif field not in before.source or before.source[field] != value:
                        changes.append(
                            FieldChange(
                                field=FieldName(field),
                                before_present=field in before.source,
                                before=before.source.get(field),
                                after=value,
                            )
                        )
                        candidate[field] = value
                repairs[identity] = before.model_copy(update={"source": candidate})
                diffs.append(RepairDiff(id=identity, changes=changes))
        if set(repairs) != set(originals) or not repairs:
            raise ValueError("Congress 114 source/CSV identity sets differ")
        return repairs, diffs


class GraphRepairRehearsal:
    """Exercises frozen repairs and rollback only in fresh indices on another cluster."""

    def __init__(self, client: Elasticsearch) -> None:
        self.client = client

    def _write(self, index: str, documents: Iterable[StoredDocument]) -> None:
        bulk(
            self.client,
            (
                {
                    "_op_type": "index",
                    "_index": index,
                    "_id": doc.id,
                    "_source": doc.source,
                }
                for doc in documents
            ),
            raise_on_error=True,
            raise_on_exception=True,
        )
        self.client.indices.refresh(index=index)

    def _read(self, index: str) -> dict[RecordId, StoredDocument]:
        return RepairBundle.unique(
            GraphRepairCapture.read_documents(self.client, index, {"match_all": {}})
        )

    @staticmethod
    def _require_sources(
        actual: dict[RecordId, StoredDocument], expected: dict[RecordId, StoredDocument]
    ) -> None:
        if {key: doc.source for key, doc in actual.items()} != {
            key: doc.source for key, doc in expected.items()
        }:
            raise ValueError("Isolated source restoration/content verification failed")

    def run(self, root: Path, output: Path) -> RehearsalReport:
        bundle = RepairBundle(root)
        material = bundle.material()
        manifest = material.manifest
        manifest_seal = FileSeal.read(root / BundleFile.MANIFEST)
        state = material.state
        cluster = ClusterIdentity.model_validate(self.client.info().body)
        if cluster == state.cluster:
            raise ValueError(
                "Rehearsal must use a different cluster UUID; no writes permitted"
            )
        originals, repairs = material.originals, material.repairs
        result = RepairBundle(output)
        result.create()
        nonce = uuid4().hex
        source_index = f"graph-rehearsal-source-{nonce}"
        settings = GraphStoreConfig(
            index=f"graph-rehearsal-{nonce}",
            first_congress=manifest.config.first_congress,
        )
        store = GraphStore(self.client, settings)
        created: list[str] = []
        try:
            for index, mapping in [
                (source_index, state.indices[IndexRole.SOURCE].mappings),
                (store.index, load_definitions()["analysis_graph"]["mappings"]),
            ]:
                definition = deepcopy(mapping)
                definition["_meta"] = {"graph_rehearsal_owner": nonce}
                self.client.indices.create(
                    index=index,
                    mappings=definition,
                    settings={"number_of_shards": 1, "number_of_replicas": 0},
                )
                created.append(index)
            self._write(source_index, originals.values())
            self._write(
                store.index,
                (pointer for pointer in state.pointers.values() if pointer is not None),
            )
            self._write(source_index, repairs.values())
            expected = originals | repairs
            self._require_sources(self._read(source_index), expected)
            job = GraphBuildJob(
                store,
                BillSignatureReader(self.client),
                RollCallReader(self.client, settings, index=source_index),
                TopicModelReader(self.client, store.index),
                lambda _progress: None,
            )
            staged = job.stage(Signal.VOTING)
            self.client.indices.refresh(index=store.index)
            self._require_sources(
                self._read_pointers(store.index),
                {doc.id: doc for doc in state.pointers.values() if doc is not None},
            )
            query: JsonObject = {
                "nested": {
                    "path": "by_congress",
                    "query": {
                        "term": {"by_congress.congress": manifest.config.congress}
                    },
                }
            }
            evidence = self.client.search(
                index=store.index,
                size=0,
                track_total_hits=True,
                allow_partial_search_results=False,
                query=query,
            )
            SearchCompletion.model_validate(evidence.body).require_complete()
            congress_edges = int(evidence["hits"]["total"]["value"])
            if (
                staged.written <= 0
                or store.edge_count(Signal.VOTING, staged.pointer.graph_version)
                != staged.written
                or congress_edges <= 0
            ):
                raise ValueError(
                    "Candidate graph count or searchable Congress evidence failed"
                )
            congresses = sorted(
                {
                    RepairIdentity.model_validate(doc.source).congress
                    for doc in expected.values()
                }
            )
            if staged.pointer.congresses != congresses:
                raise ValueError(
                    "Candidate graph does not cover the frozen input scope"
                )

            if (
                result.write_rows(
                    BundleFile.EDGES, self._edges(store.index, staged.pointer)
                )
                != staged.written
            ):
                raise ValueError("Candidate export count does not match written edges")
            result.write(BundleFile.POINTER, staged.pointer)
            store.publish(staged.pointer)
            for identity, before in originals.items():
                if identity in repairs:
                    current = StoredDocument.model_validate(
                        self.client.get(index=source_index, id=identity).body
                    )
                    if current.source != repairs[identity].source:
                        raise ValueError(
                            "Concurrent source change during rollback rehearsal"
                        )
                    self.client.index(
                        index=source_index,
                        id=identity,
                        document=before.source,
                        if_seq_no=current.seq_no,
                        if_primary_term=current.primary_term,
                    )
            pointer_id = GraphVersionPointer.pointer_id(Signal.VOTING)
            current = StoredDocument.model_validate(
                self.client.get(index=store.index, id=pointer_id).body
            )
            if current.source != staged.pointer.model_dump(mode="json"):
                raise ValueError("Concurrent pointer change during rollback rehearsal")
            before_pointer = state.pointers[Signal.VOTING]
            if before_pointer is None:
                self.client.delete(
                    index=store.index,
                    id=pointer_id,
                    if_seq_no=current.seq_no,
                    if_primary_term=current.primary_term,
                )
            else:
                self.client.index(
                    index=store.index,
                    id=pointer_id,
                    document=before_pointer.source,
                    if_seq_no=current.seq_no,
                    if_primary_term=current.primary_term,
                )
            self.client.indices.refresh(index=[source_index, store.index])
            self._require_sources(self._read(source_index), originals)
            self._require_sources(
                self._read_pointers(store.index),
                {doc.id: doc for doc in state.pointers.values() if doc is not None},
            )
            bundle.verify()
            if FileSeal.read(root / BundleFile.MANIFEST) != manifest_seal:
                raise ValueError("Bundle manifest changed during rehearsal")
            report = RehearsalReport(
                bundle_id=manifest.bundle_id,
                bundle_manifest=manifest_seal,
                source_cluster_uuid=state.cluster.cluster_uuid,
                staging_cluster_uuid=cluster.cluster_uuid,
                source_records=len(originals),
                repaired_records=len(repairs),
                graph_version=staged.pointer.graph_version,
                edge_count=staged.written,
                congresses=congresses,
                congress_114_edges=congress_edges,
                candidate_files=[
                    FileSeal.read(output / name)
                    for name in (BundleFile.EDGES, BundleFile.POINTER)
                ],
            )
        finally:
            for index in reversed(created):
                mapping = self.client.indices.get_mapping(index=index)[index][
                    "mappings"
                ]
                if mapping.get("_meta", {}).get("graph_rehearsal_owner") != nonce:
                    raise ValueError(f"Refusing cleanup of non-owned index: {index}")
                self.client.indices.delete(index=index)
        result.write(BundleFile.REPORT, report)
        return report

    def _read_pointers(self, index: str) -> dict[RecordId, StoredDocument]:
        return RepairBundle.unique(
            GraphRepairCapture.read_documents(
                self.client, index, {"term": {"kind": "pointer"}}
            )
        )

    def _edges(self, index: str, pointer: GraphVersionPointer) -> Iterator[MemberEdge]:
        seen: set[str] = set()
        for hit in scan(
            self.client,
            index=index,
            query={"query": {"term": {"kind": "edge"}}},
            allow_partial_search_results=False,
        ):
            edge = MemberEdge.model_validate(hit["_source"])
            if (
                edge.id != hit["_id"]
                or edge.id in seen
                or edge.graph_version != pointer.graph_version
                or edge.signal is not Signal.VOTING
                or not math.isfinite(edge.score)
                or not 0 <= edge.score <= 1
                or any(
                    not math.isfinite(stats.score) or not 0 <= stats.score <= 1
                    for stats in edge.by_congress
                )
            ):
                raise ValueError("Invalid candidate edge identity/version/score")
            seen.add(edge.id)
            yield edge

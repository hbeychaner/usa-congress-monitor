"""Sealed voting-only staging and compare-and-swap pointer publication."""

from __future__ import annotations

import math
from base64 import b64decode
from collections.abc import Iterator
from datetime import UTC, datetime
from enum import StrEnum
from itertools import batched
from pathlib import Path
from typing import Literal

from elasticsearch.helpers import bulk
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, TypeAdapter

from cdm.contracts.analysis import AnalysisState
from cdm.contracts.api import NeighborhoodResponse
from cdm.graph.live_repair import (
    AppliedRepair,
    DocumentBatch,
    DocumentCount,
    GraphBackup,
    LiveGraphRepair,
    RepairReceipt,
    RepairStart,
)
from cdm.graph.models import GraphVersionPointer, MemberEdge, Signal
from cdm.graph.repair import (
    BundleFile,
    FileSeal,
    IndexRole,
    RecordId,
    RepairBundle,
    RepairIdentity,
    StoredDocument,
)
from cdm.store.client import SearchCompletion
from cdm.utils.json_types import JsonObject, JsonValue


class VotingPromotionPlan(BaseModel):
    schema_version: Literal[1] = 1
    prepared_at: AwareDatetime
    applied_repair: FileSeal
    candidate_files: list[FileSeal]
    pointer: GraphVersionPointer
    before: StoredDocument
    edge_count: int = Field(gt=0)
    by_congress: dict[int, int]
    sample_member: str = Field(min_length=1)


class VotingStage(BaseModel):
    plan: FileSeal
    documents: FileSeal
    staged_at: AwareDatetime
    edge_count: int = Field(gt=0)


class VotingServingAcceptance(BaseModel):
    stage: FileSeal
    member: str = Field(min_length=1)
    congress: Literal[114] = 114
    api_verified: Literal[True]
    desktop_verified: Literal[True]
    narrow_verified: Literal[True]
    verified_at: AwareDatetime
    browser_report: FileSeal


class BrowserAttachment(BaseModel):
    name: str
    body: str | None = None


class BrowserAttempt(BaseModel):
    status: Literal["passed"]
    retry: Literal[0]
    errors: list[JsonValue] = Field(max_length=0)
    attachments: list[BrowserAttachment]

    def require_graph(self, pointer: GraphVersionPointer, member: str) -> None:
        responses = [
            item for item in self.attachments if item.name == "neighborhood.json"
        ]
        if len(responses) != 1 or responses[0].body is None:
            raise ValueError("Real browser API response evidence is missing")
        graph = NeighborhoodResponse.model_validate_json(
            b64decode(responses[0].body, validate=True)
        )
        voting = graph.analysis.get(Signal.VOTING)
        if (
            graph.congress != 114
            or graph.versions.get(Signal.VOTING) != pointer.graph_version
            or voting is None
            or voting.state is not AnalysisState.AVAILABLE
            or not any(
                node.is_seed and node.member.bioguide_id == member
                for node in graph.nodes
            )
            or not graph.links
            or not any(
                link.signal_scores.get(Signal.VOTING, 0) > 0 for link in graph.links
            )
            or any(
                not math.isfinite(score) or not 0 <= score <= 1
                for link in graph.links
                for score in [link.score, *link.signal_scores.values()]
            )
        ):
            raise ValueError("Real API acceptance does not match staged voting graph")


class BrowserViewport(StrEnum):
    DESKTOP = "desktop"
    NARROW = "narrow"


class BrowserCase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    project: BrowserViewport = Field(validation_alias="projectName")
    status: Literal["expected"]
    results: list[BrowserAttempt] = Field(min_length=1, max_length=1)


class BrowserSpec(BaseModel):
    ok: Literal[True]
    tests: list[BrowserCase]


class BrowserSuite(BaseModel):
    file: str
    specs: list[BrowserSpec]


class BrowserAcceptance(BaseModel):
    suites: list[BrowserSuite]
    errors: list[JsonValue] = Field(max_length=0)

    def require_viewports(self, pointer: GraphVersionPointer, member: str) -> None:
        cases = [
            case for suite in self.suites for spec in suite.specs for case in spec.tests
        ]
        if (
            len(cases) != 2
            or {case.project for case in cases} != set(BrowserViewport)
            or any(
                Path(suite.file).name != "live-voting.spec.ts" for suite in self.suites
            )
        ):
            raise ValueError(
                "Both real voting browser viewports must pass without retries"
            )
        for case in cases:
            case.results[0].require_graph(pointer, member)


class VotingPublication(BaseModel):
    plan: FileSeal
    receipt: FileSeal
    finished_at: AwareDatetime
    version: str
    edge_count: int
    rolled_back: bool


class VotingGraphPromotion:
    def __init__(self, repair: LiveGraphRepair) -> None:
        self.repair = repair
        self.client = repair.client

    @staticmethod
    def _query(version: str) -> JsonObject:
        return {
            "bool": {
                "filter": [
                    {"term": {"kind": "edge"}},
                    {"term": {"signal": Signal.VOTING}},
                    {"term": {"graph_version": version}},
                ]
            }
        }

    @staticmethod
    def _edges(candidate: Path, pointer: GraphVersionPointer) -> Iterator[MemberEdge]:
        seen: set[str] = set()
        parser = TypeAdapter(JsonObject)
        with (candidate / BundleFile.EDGES).open() as handle:
            for line in handle:
                source = parser.validate_json(line)
                edge = MemberEdge.model_validate(source)
                if (
                    source != edge.model_dump(mode="json")
                    or edge.id in seen
                    or edge.signal is not Signal.VOTING
                    or edge.graph_version != pointer.graph_version
                    or not edge.member
                    or not edge.neighbor
                    or edge.member == edge.neighbor
                    or not math.isfinite(edge.score)
                    or not 0 <= edge.score <= 1
                    or not edge.by_congress
                    or len({stats.congress for stats in edge.by_congress})
                    != len(edge.by_congress)
                    or any(
                        stats.congress not in (pointer.congresses or [])
                        or not math.isfinite(stats.score)
                        or not 0 <= stats.score <= 1
                        or not 0 <= stats.agreed_votes <= stats.shared_votes
                        or not 0
                        <= stats.agreed_split_votes
                        <= stats.shared_split_votes
                        <= stats.shared_votes
                        or stats.shared_votes <= 0
                        or not math.isfinite(stats.co_signed)
                        for stats in edge.by_congress
                    )
                ):
                    raise ValueError(
                        "Invalid sealed voting edge identity/scope/score/evidence"
                    )
                seen.add(edge.id)
                yield edge

    def _candidate(
        self, applied: AppliedRepair, candidate: Path
    ) -> VotingPromotionPlan:
        report = applied.plan.rehearsal
        if len(report.candidate_files) != 2 or {
            seal.name for seal in report.candidate_files
        } != {BundleFile.EDGES, BundleFile.POINTER}:
            raise ValueError("Incomplete accepted candidate seals")
        for seal in report.candidate_files:
            if FileSeal.read(candidate / seal.name) != seal:
                raise ValueError("Accepted voting candidate changed")
        pointer = GraphVersionPointer.model_validate_json(
            (candidate / BundleFile.POINTER).read_text()
        )
        before = applied.material.state.pointers[Signal.VOTING]
        scope = sorted(
            {
                RepairIdentity.model_validate(doc.source).congress
                for doc in applied.material.originals.values()
            }
        )
        if (
            before is None
            or pointer.signal is not Signal.VOTING
            or pointer.source_model_version is not None
            or pointer.congresses != scope
            or report.congresses != scope
            or pointer.graph_version != report.graph_version
            or pointer.graph_version == before.source.get("graph_version")
            or applied.plan.graph_records + report.edge_count
            > applied.material.manifest.config.max_graph_records
        ):
            raise ValueError("Voting candidate pointer/scope/budget is not approved")
        counts = dict.fromkeys(scope, 0)
        count = 0
        member = ""
        for edge in self._edges(candidate, pointer):
            count += 1
            for stats in edge.by_congress:
                counts[stats.congress] += 1
                if (
                    stats.congress == applied.material.manifest.config.congress
                    and not member
                ):
                    member = edge.member
        if (
            count != report.edge_count
            or counts.get(114) != report.congress_114_edges
            or not all(counts.values())
        ):
            raise ValueError("Voting candidate counts/coverage do not match acceptance")
        return VotingPromotionPlan(
            prepared_at=datetime.now(UTC),
            applied_repair=applied.report_seal,
            candidate_files=report.candidate_files,
            pointer=pointer,
            before=before,
            edge_count=count,
            by_congress=counts,
            sample_member=member,
        )

    def _documents(
        self, index: str, candidate: Path, plan: VotingPromotionPlan
    ) -> Iterator[StoredDocument]:
        for batch in batched(self._edges(candidate, plan.pointer), 500):
            expected = {
                RecordId(edge.id): edge.model_dump(mode="json") for edge in batch
            }
            documents = DocumentBatch.model_validate(
                self.client.mget(index=index, ids=list(expected)).body
            ).docs
            actual = RepairBundle.unique(documents)
            if {key: doc.source for key, doc in actual.items()} != expected:
                raise ValueError(
                    "Staged voting documents do not match sealed candidate"
                )
            yield from documents

    def _preserved(
        self,
        applied: AppliedRepair,
        repair_output: Path,
        output: Path,
        plan: VotingPromotionPlan,
        pointer: StoredDocument | None = None,
    ) -> None:
        index = applied.material.state.indices[IndexRole.GRAPH].name
        GraphBackup(
            self.client, RepairBundle(repair_output), applied.plan.graph_records
        ).verify(
            index,
            versions=True,
            extra_records=plan.edge_count,
            voting_pointer=pointer,
        )
        GraphBackup(
            self.client,
            RepairBundle(output),
            plan.edge_count,
            BundleFile.STAGED_DOCUMENTS,
        ).verify(
            index,
            versions=True,
            extra_records=applied.plan.graph_records,
        )
        if (
            DocumentCount.read(
                self.client, index, self._query(plan.pointer.graph_version)
            )
            != plan.edge_count
        ):
            raise ValueError("Staged voting edge count changed")
        for congress, count in plan.by_congress.items():
            query: JsonObject = {
                "bool": {
                    "filter": [
                        self._query(plan.pointer.graph_version),
                        {
                            "nested": {
                                "path": "by_congress",
                                "query": {"term": {"by_congress.congress": congress}},
                            }
                        },
                    ]
                }
            }
            result = self.client.search(
                index=index,
                size=0,
                track_total_hits=True,
                allow_partial_search_results=False,
                query=query,
            )
            SearchCompletion.model_validate(result.body).require_complete()
            if result["hits"]["total"]["value"] != count:
                raise ValueError("Searchable voting Congress evidence changed")

    def stage(
        self, root: Path, repair_output: Path, candidate: Path, output: Path
    ) -> VotingStage:
        applied = self.repair.require_applied(root, repair_output)
        plan = self._candidate(applied, candidate)
        index = applied.material.state.indices[IndexRole.GRAPH].name
        if DocumentCount.read(
            self.client, index, self._query(plan.pointer.graph_version)
        ):
            raise ValueError(
                "Candidate voting version already exists; refusing overwrite"
            )
        GraphBackup(
            self.client, RepairBundle(repair_output), applied.plan.graph_records
        ).verify(index, versions=True)
        result = RepairBundle(output)
        result.create()
        result.write(BundleFile.PROMOTION_PLAN, plan)
        written, _ = bulk(
            self.client,
            (
                {
                    "_op_type": "create",
                    "_index": index,
                    "_id": edge.id,
                    "_source": edge.model_dump(mode="json"),
                }
                for edge in self._edges(candidate, plan.pointer)
            ),
            raise_on_error=True,
            raise_on_exception=True,
        )
        if written != plan.edge_count:
            raise ValueError("Incomplete voting staging writes")
        self.client.indices.refresh(index=index)
        if (
            result.write_rows(
                BundleFile.STAGED_DOCUMENTS, self._documents(index, candidate, plan)
            )
            != plan.edge_count
        ):
            raise ValueError("Incomplete staged voting before-images")
        self.repair.require_applied(root, repair_output)
        for seal in plan.candidate_files:
            if FileSeal.read(candidate / seal.name) != seal:
                raise ValueError("Candidate changed during staging")
        self._preserved(applied, repair_output, output, plan)
        stage = VotingStage(
            plan=FileSeal.read(output / BundleFile.PROMOTION_PLAN),
            documents=FileSeal.read(output / BundleFile.STAGED_DOCUMENTS),
            staged_at=datetime.now(UTC),
            edge_count=written,
        )
        result.write(BundleFile.STAGED, stage)
        return stage

    @staticmethod
    def _load(output: Path) -> tuple[VotingPromotionPlan, VotingStage]:
        if output.is_symlink():
            raise ValueError("Promotion evidence directory must not be a symlink")
        FileSeal.read(output / BundleFile.STAGED)
        stage = VotingStage.model_validate_json(
            (output / BundleFile.STAGED).read_text()
        )
        if stage.plan != FileSeal.read(
            output / BundleFile.PROMOTION_PLAN
        ) or stage.documents != FileSeal.read(output / BundleFile.STAGED_DOCUMENTS):
            raise ValueError("Staged voting evidence changed")
        plan = VotingPromotionPlan.model_validate_json(
            (output / BundleFile.PROMOTION_PLAN).read_text()
        )
        if (
            plan.edge_count != stage.edge_count
            or plan.pointer.signal is not Signal.VOTING
        ):
            raise ValueError("Staged voting plan/count/signal changed")
        return plan, stage

    def accept(
        self,
        root: Path,
        repair_output: Path,
        output: Path,
        browser_report: Path,
    ) -> VotingServingAcceptance:
        plan, _stage = self._load(output)
        if browser_report.parent.resolve() != output.resolve():
            raise ValueError(
                "Browser report must reside in the promotion evidence directory"
            )
        seal = FileSeal.read(browser_report)
        BrowserAcceptance.model_validate_json(
            browser_report.read_text()
        ).require_viewports(
            plan.pointer,
            plan.sample_member,
        )
        applied = self.repair.require_applied(root, repair_output)
        if applied.report_seal != plan.applied_repair:
            raise ValueError("Serving acceptance is not bound to the applied repair")
        acceptance = VotingServingAcceptance(
            stage=FileSeal.read(output / BundleFile.STAGED),
            member=plan.sample_member,
            api_verified=True,
            desktop_verified=True,
            narrow_verified=True,
            verified_at=datetime.now(UTC),
            browser_report=seal,
        )
        RepairBundle(output).write(BundleFile.SERVING_ACCEPTANCE, acceptance)
        return acceptance

    def publish(
        self, root: Path, repair_output: Path, output: Path, *, rollback: bool = False
    ) -> VotingPublication:
        plan, _stage = self._load(output)
        expected = plan.before
        if rollback:
            FileSeal.read(output / BundleFile.PROMOTION_RECEIPT)
            expected = StoredDocument.model_validate_json(
                (output / BundleFile.PROMOTION_RECEIPT).read_text()
            )
            if expected.source != plan.pointer.model_dump(mode="json"):
                raise ValueError("Voting promotion receipt does not match candidate")
        else:
            FileSeal.read(output / BundleFile.SERVING_ACCEPTANCE)
            acceptance = VotingServingAcceptance.model_validate_json(
                (output / BundleFile.SERVING_ACCEPTANCE).read_text()
            )
            if (
                acceptance.stage != FileSeal.read(output / BundleFile.STAGED)
                or acceptance.member != plan.sample_member
            ):
                raise ValueError(
                    "Serving acceptance is not bound to staged voting graph"
                )
            if (
                FileSeal.read(output / acceptance.browser_report.name)
                != acceptance.browser_report
            ):
                raise ValueError("Serving acceptance evidence changed")
            BrowserAcceptance.model_validate_json(
                (output / acceptance.browser_report.name).read_text()
            ).require_viewports(plan.pointer, plan.sample_member)
        applied = self.repair.require_applied(
            root, repair_output, voting_pointer=expected
        )
        accepted = applied.plan.rehearsal
        if (
            applied.report_seal != plan.applied_repair
            or plan.before != applied.material.state.pointers[Signal.VOTING]
            or plan.pointer.graph_version != accepted.graph_version
            or plan.pointer.congresses != accepted.congresses
            or plan.pointer.source_model_version is not None
            or plan.edge_count != accepted.edge_count
            or plan.by_congress.get(114) != accepted.congress_114_edges
            or set(plan.by_congress) != set(accepted.congresses)
            or plan.candidate_files != accepted.candidate_files
        ):
            raise ValueError("Voting stage is not bound to the applied repair")
        self._preserved(applied, repair_output, output, plan, expected)
        result = RepairBundle(output)
        started = (
            BundleFile.POINTER_ROLLBACK_STARTED
            if rollback
            else BundleFile.PROMOTION_STARTED
        )
        result.write(
            started,
            RepairStart(
                started_at=datetime.now(UTC),
                plan=FileSeal.read(output / BundleFile.STAGED),
            ),
        )
        body = plan.before.source if rollback else plan.pointer.model_dump(mode="json")
        write = RepairReceipt.model_validate(
            self.client.index(
                index=applied.material.state.indices[IndexRole.GRAPH].name,
                id=expected.id,
                document=body,
                if_seq_no=expected.seq_no,
                if_primary_term=expected.primary_term,
                refresh=True,
            ).body
        )
        if write.id != expected.id:
            raise ValueError("Voting pointer write response identity mismatch")
        current = StoredDocument(
            id=write.id,
            source=body,
            seq_no=write.seq_no,
            primary_term=write.primary_term,
        )
        receipt = (
            BundleFile.POINTER_ROLLBACK_RECEIPT
            if rollback
            else BundleFile.PROMOTION_RECEIPT
        )
        result.write(receipt, current)
        self.repair.require_applied(root, repair_output, voting_pointer=current)
        self._preserved(applied, repair_output, output, plan, current)
        report = VotingPublication(
            plan=FileSeal.read(output / BundleFile.STAGED),
            receipt=FileSeal.read(output / receipt),
            finished_at=datetime.now(UTC),
            version=GraphVersionPointer.model_validate(body).graph_version,
            edge_count=plan.edge_count,
            rolled_back=rollback,
        )
        result.write(
            BundleFile.POINTER_ROLLED_BACK if rollback else BundleFile.PROMOTED, report
        )
        return report

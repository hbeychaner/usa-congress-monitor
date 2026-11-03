import os
from base64 import b64decode, b64encode
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from elastic_transport import ObjectApiResponse
from elasticsearch import ConflictError, Elasticsearch

from cdm.config.topic_analysis import GraphRepairConfig, GraphRepairMappingField
from cdm.contracts.analysis import AnalysisState, AnalysisStatus
from cdm.contracts.api import GraphLink, GraphNode, MemberSummary, NeighborhoodResponse
from cdm.graph.job import GraphBuildJob
from cdm.graph.live_repair import LiveGraphRepair
from cdm.graph.models import (
    CongressEdgeStats,
    GraphVersionPointer,
    MemberEdge,
    PartyGroup,
    Signal,
)
from cdm.graph.promotion import (
    BrowserAcceptance,
    BrowserAttachment,
    BrowserAttempt,
    BrowserCase,
    BrowserSpec,
    BrowserSuite,
    BrowserViewport,
    VotingGraphPromotion,
    VotingServingAcceptance,
)
from cdm.graph.repair import (
    BundleFile,
    FileSeal,
    GraphRepairCapture,
    GraphRepairRehearsal,
    RecordId,
    RehearsalReport,
    RepairBundle,
    StoredDocument,
)
from cdm.graph.store import GraphStore
from cdm.ingest.voteview import (
    Chamber,
    CsvFile,
    CsvKind,
    Position,
    RollCallBuilder,
    RollCallDocument,
)
from cdm.store.index_manager import load_definitions
from cdm.utils.json_types import JsonObject


class RepairFixture:
    def __init__(
        self, source: Elasticsearch, staging: Elasticsearch, root: Path
    ) -> None:
        self.source = source
        self.staging = staging
        self.root = root
        self.source_index = f"graph-repair-source-{uuid4().hex}"
        self.graph_index = f"graph-repair-original-{uuid4().hex}"
        self.config = GraphRepairConfig(
            cache_dir=root, expected_house=1, expected_senate=1, max_source_records=10
        )
        source.indices.create(index=self.source_index, **load_definitions()["rollcall"])
        source.indices.create(
            index=self.graph_index, **load_definitions()["analysis_graph"]
        )
        for chamber in Chamber:
            for kind in CsvKind:
                path = root / CsvFile(kind=kind, chamber=chamber, congress=114).name
                if kind is CsvKind.MEMBERS:
                    path.write_text(
                        f"chamber,icpsr,party_code,bioguide_id\n{chamber},1,100,A\n{chamber},2,200,B\n"
                    )
                elif kind is CsvKind.ROLLCALLS:
                    path.write_text(f"congress,chamber,rollnumber\n114,{chamber},1\n")
                else:
                    path.write_text("rollnumber,icpsr,cast_code\n1,1.0,1\n1,2.0,6\n")
            files = {
                kind: root / CsvFile(kind=kind, chamber=chamber, congress=114).name
                for kind in CsvKind
            }
            doc = next(
                RollCallBuilder(
                    files[CsvKind.MEMBERS],
                    files[CsvKind.ROLLCALLS],
                    files[CsvKind.VOTES],
                ).build()
            )
            doc.positions = {position: [] for position in Position}
            doc.party_positions = {}
            doc.party_split = False
            body = doc.to_index_document()
            body["retained_extra"] = "preserve this"
            source.index(index=self.source_index, id=doc.id, document=body)
        older = RollCallDocument(congress=113, chamber=Chamber.HOUSE, roll_number=1)
        older.positions[Position.YEA] = ["A"]
        older.positions[Position.NAY] = ["B"]
        older.party_split = True
        source.index(
            index=self.source_index, id=older.id, document=older.to_index_document()
        )
        self.pointer = GraphVersionPointer(
            signal=Signal.VOTING, graph_version="original"
        )
        source.index(
            index=self.graph_index,
            id=self.pointer.id,
            document=self.pointer.model_dump(mode="json"),
        )
        source.indices.refresh(index=[self.source_index, self.graph_index])
        self.capture = GraphRepairCapture(
            source,
            self.config,
            source_index=self.source_index,
            graph_index=self.graph_index,
        )

    def documents(self) -> dict[RecordId, JsonObject]:
        return {
            doc.id: doc.source
            for doc in GraphRepairCapture.read_documents(
                self.source, self.source_index, {"match_all": {}}
            )
        }

    def bundle(self) -> Path:
        output = self.root / "capture"
        self.capture.capture(output)
        return output


@pytest.fixture
def repair(tmp_path: Path) -> Iterator[RepairFixture]:
    source_url = os.environ.get("GRAPH_REPAIR_SOURCE_TEST_URL")
    staging_url = os.environ.get("GRAPH_REPAIR_STAGING_TEST_URL")
    if not source_url or not staging_url:
        pytest.skip("Set two isolated GRAPH_REPAIR_{SOURCE,STAGING}_TEST_URL endpoints")
    with Elasticsearch(source_url) as source, Elasticsearch(staging_url) as staging:
        fixture = RepairFixture(source, staging, tmp_path)
        try:
            yield fixture
        finally:
            source.indices.delete(
                index=[fixture.source_index, fixture.graph_index],
                ignore_unavailable=True,
            )


def test_capture_and_rehearsal_restore_exact_images_without_serving_writes(
    repair: RepairFixture,
) -> None:
    before = repair.documents()
    with patch.object(repair.source, "index", wraps=repair.source.index) as write:
        root = repair.bundle()
        write.assert_not_called()
    manifest = RepairBundle(root).verify()
    assert manifest.source_records == 3
    assert manifest.repair_records == 2
    output = repair.root / "rehearsal"
    report = GraphRepairRehearsal(repair.staging).run(root, output)
    assert report.edge_count == 2
    assert report.congresses == [113, 114]
    assert report.congress_114_edges == 2
    assert report.rollback_verified
    assert not report.live_writes_performed
    assert (
        RehearsalReport.model_validate_json((output / BundleFile.REPORT).read_text())
        == report
    )
    assert repair.documents() == before
    assert repair.source.get(index=repair.graph_index, id=repair.pointer.id)[
        "_source"
    ] == repair.pointer.model_dump(mode="json")
    assert (
        repair.staging.indices.get(
            index="graph-rehearsal-source-*", allow_no_indices=True
        ).body
        == {}
    )
    assert (
        repair.staging.indices.get(
            index="congress-graph-rehearsal-*", allow_no_indices=True
        ).body
        == {}
    )


def test_same_cluster_rejected_before_any_target_mutation(
    repair: RepairFixture,
) -> None:
    root = repair.bundle()
    with patch.object(
        repair.source.indices, "create", wraps=repair.source.indices.create
    ) as create:
        with pytest.raises(ValueError, match="different cluster UUID"):
            GraphRepairRehearsal(repair.source).run(root, repair.root / "forbidden")
        create.assert_not_called()
    assert not (repair.root / "forbidden").exists()


@pytest.mark.parametrize(
    "filename",
    [BundleFile.SOURCE, BundleFile.REPAIRS, BundleFile.DIFFS, "H114_votes.csv"],
)
def test_tampered_bundle_is_rejected(repair: RepairFixture, filename: str) -> None:
    root = repair.bundle()
    with (root / filename).open("a") as handle:
        handle.write("\n")
    with pytest.raises(ValueError, match="checksum mismatch"):
        GraphRepairRehearsal(repair.staging).run(root, repair.root / "invalid")
    assert not (repair.root / "invalid").exists()


def test_unexplained_metadata_change_prevents_success_manifest(
    repair: RepairFixture,
) -> None:
    repair.source.update(
        index=repair.source_index,
        id="rollcall:114:house:1",
        doc={"description": "unexpected metadata"},
        refresh=True,
    )
    with pytest.raises(ValueError, match="Unexplained metadata difference"):
        repair.bundle()
    assert not (repair.root / "capture" / BundleFile.MANIFEST).exists()


def test_identity_mismatch_prevents_success_manifest(repair: RepairFixture) -> None:
    repair.source.delete(
        index=repair.source_index, id="rollcall:114:house:1", refresh=True
    )
    with pytest.raises(ValueError, match="repair identity"):
        repair.bundle()
    assert not (repair.root / "capture" / BundleFile.MANIFEST).exists()


def test_existing_capture_is_never_overwritten(repair: RepairFixture) -> None:
    root = repair.bundle()
    before = (root / BundleFile.MANIFEST).read_bytes()
    with pytest.raises(FileExistsError):
        repair.capture.capture(root)
    assert (root / BundleFile.MANIFEST).read_bytes() == before


def test_failure_cannot_publish_or_leave_owned_scratch_indices(
    repair: RepairFixture,
) -> None:
    root = repair.bundle()
    before = repair.documents()
    with (
        patch.object(
            GraphBuildJob,
            "stage",
            side_effect=RuntimeError("injected candidate failure"),
        ),
        pytest.raises(RuntimeError, match="injected candidate failure"),
    ):
        GraphRepairRehearsal(repair.staging).run(root, repair.root / "failed")
    assert repair.documents() == before
    assert not (repair.root / "failed" / BundleFile.REPORT).exists()
    assert (
        repair.staging.indices.get(
            index="graph-rehearsal-source-*", allow_no_indices=True
        ).body
        == {}
    )
    assert (
        repair.staging.indices.get(
            index="congress-graph-rehearsal-*", allow_no_indices=True
        ).body
        == {}
    )


def test_rollback_handles_previously_absent_pointer(repair: RepairFixture) -> None:
    repair.source.delete(index=repair.graph_index, id=repair.pointer.id, refresh=True)
    root = repair.bundle()
    assert (
        GraphRepairRehearsal(repair.staging)
        .run(root, repair.root / "no-pointer")
        .rollback_verified
    )

    assert not repair.source.exists(index=repair.graph_index, id=repair.pointer.id)


def test_pointer_drift_cannot_complete_capture(repair: RepairFixture) -> None:
    state = repair.capture._state()
    changed = state.model_copy(deep=True)
    changed.pointers[Signal.VOTING] = None
    with (
        patch.object(repair.capture, "_state", side_effect=[state, changed]),
        pytest.raises(ValueError, match="pointers changed during capture"),
    ):
        repair.bundle()
    assert not (repair.root / "capture" / BundleFile.MANIFEST).exists()


@pytest.mark.parametrize("pointer_conflict", [False, True])
def test_concurrent_change_blocks_rollback_acceptance(
    repair: RepairFixture, pointer_conflict: bool
) -> None:
    root = repair.bundle()
    before = repair.documents()
    publish = GraphStore.publish

    def publish_then_conflict(store: GraphStore, pointer: GraphVersionPointer) -> None:
        publish(store, pointer)
        if pointer_conflict:
            index = store.index
            identity = pointer.id
        else:
            names = list(repair.staging.indices.get(index="graph-rehearsal-source-*"))
            assert len(names) == 1
            index = names[0]
            identity = "rollcall:114:house:1"
        body = StoredDocument.model_validate(
            repair.staging.get(index=index, id=identity).body
        ).source
        body["concurrent_marker"] = True
        repair.staging.index(index=index, id=identity, document=body, refresh=True)

    with (
        patch.object(
            GraphStore, "publish", autospec=True, side_effect=publish_then_conflict
        ),
        pytest.raises(ValueError, match="Concurrent .* change during rollback"),
    ):
        GraphRepairRehearsal(repair.staging).run(root, repair.root / "conflict")
    assert repair.documents() == before
    assert not (repair.root / "conflict" / BundleFile.REPORT).exists()
    assert (
        repair.staging.indices.get(
            index="graph-rehearsal-source-*", allow_no_indices=True
        ).body
        == {}
    )
    assert (
        repair.staging.indices.get(
            index="congress-graph-rehearsal-*", allow_no_indices=True
        ).body
        == {}
    )
    assert repair.source.get(index=repair.graph_index, id=repair.pointer.id)[
        "_source"
    ] == repair.pointer.model_dump(mode="json")


class LiveRepairFixture:
    def __init__(self, fixture: RepairFixture) -> None:
        self.fixture = fixture
        definition = deepcopy(load_definitions()["analysis_graph"])
        for field in GraphRepairMappingField:
            parts = field.split(".")
            properties = definition["mappings"]["properties"]
            for name in parts[:-1]:
                properties = properties[name]["properties"]
            del properties[parts[-1]]
        fixture.source.indices.delete(index=fixture.graph_index)
        fixture.source.indices.create(index=fixture.graph_index, **definition)
        self.edge = MemberEdge(
            graph_version="original",
            signal=Signal.VOTING,
            member="A",
            neighbor="B",
            score=0.5,
            by_congress=[CongressEdgeStats(congress=114, shared_votes=7)],
        )
        for document in (fixture.pointer, self.edge):
            fixture.source.index(
                index=fixture.graph_index,
                id=document.id,
                document=document.model_dump(mode="json"),
            )
        fixture.source.indices.refresh(index=fixture.graph_index)
        self.root = fixture.bundle()
        self.accepted = fixture.root / "accepted"
        self.output = fixture.root / "prepared"
        rehearsal = GraphRepairRehearsal(fixture.staging)
        rehearsal.run(self.root, self.accepted)
        self.tool = LiveGraphRepair(fixture.capture, rehearsal)

    def prepare(self) -> None:
        self.tool.prepare(self.root, self.accepted, self.output)


@pytest.fixture
def live_repair(repair: RepairFixture) -> LiveRepairFixture:
    return LiveRepairFixture(repair)


class VotingPromotionFixture:
    def __init__(self, repair: LiveRepairFixture) -> None:
        self.repair = repair
        repair.prepare()
        repair.tool.apply(repair.root, repair.output)
        self.tool = VotingGraphPromotion(repair.tool)
        self.output = repair.fixture.root / "promotion"

    def stage(self) -> None:
        self.tool.stage(
            self.repair.root, self.repair.output, self.repair.accepted, self.output
        )

    def accept(self) -> None:
        plan, _stage = self.tool._load(self.output)
        result = RepairBundle(self.output)
        graph = NeighborhoodResponse(
            seeds=[plan.sample_member],
            congress=114,
            versions={Signal.VOTING: plan.pointer.graph_version},
            analysis={Signal.VOTING: AnalysisStatus(state=AnalysisState.AVAILABLE)},
            nodes=[
                GraphNode(
                    member=MemberSummary(
                        bioguide_id=identity,
                        display_name=identity,
                        party="D",
                        state="CA",
                    ),
                    party_group=PartyGroup.DEMOCRATIC,
                    is_seed=identity == plan.sample_member,
                )
                for identity in ("A", "B")
            ],
            links=[
                GraphLink(
                    source="A",
                    target="B",
                    score=0.5,
                    signal_scores={Signal.VOTING: 0.5},
                )
            ],
        )
        result.write(
            BundleFile.SERVING_BROWSER,
            BrowserAcceptance(
                suites=[
                    BrowserSuite(
                        file="live-voting.spec.ts",
                        specs=[
                            BrowserSpec(
                                ok=True,
                                tests=[
                                    BrowserCase(
                                        project=project,
                                        status="expected",
                                        results=[
                                            BrowserAttempt(
                                                status="passed",
                                                retry=0,
                                                errors=[],
                                                attachments=[
                                                    BrowserAttachment(
                                                        name="neighborhood.json",
                                                        body=b64encode(
                                                            graph.model_dump_json().encode()
                                                        ).decode(),
                                                    )
                                                ],
                                            )
                                        ],
                                    )
                                ],
                            )
                            for project in BrowserViewport
                        ],
                    )
                ],
                errors=[],
            ),
        )
        self.tool.accept(
            self.repair.root,
            self.repair.output,
            self.output,
            self.output / BundleFile.SERVING_BROWSER,
        )

    def publish(self, *, rollback: bool = False) -> None:
        self.tool.publish(
            self.repair.root, self.repair.output, self.output, rollback=rollback
        )


@pytest.fixture
def voting_promotion(live_repair: LiveRepairFixture) -> VotingPromotionFixture:
    return VotingPromotionFixture(live_repair)


def test_voting_stage_publish_and_cas_rollback_preserve_all_other_data(
    voting_promotion: VotingPromotionFixture,
) -> None:
    fixture = voting_promotion.repair.fixture
    before = fixture.source.get(index=fixture.graph_index, id=fixture.pointer.id).body
    sources = fixture.documents()
    voting_promotion.stage()
    assert (
        fixture.source.get(index=fixture.graph_index, id=fixture.pointer.id).body
        == before
    )
    voting_promotion.accept()
    voting_promotion.publish()
    plan, stage = voting_promotion.tool._load(voting_promotion.output)
    promoted = fixture.source.get(index=fixture.graph_index, id=fixture.pointer.id)
    assert promoted["_source"] == plan.pointer.model_dump(mode="json")
    assert promoted["_seq_no"] != before["_seq_no"]
    voting_promotion.publish(rollback=True)
    assert (
        fixture.source.get(index=fixture.graph_index, id=fixture.pointer.id)["_source"]
        == before["_source"]
    )
    assert fixture.documents() == sources
    assert fixture.source.get(
        index=fixture.graph_index, id=voting_promotion.repair.edge.id
    )["_source"] == voting_promotion.repair.edge.model_dump(mode="json")
    assert (
        fixture.source.count(index=fixture.graph_index)["count"] == 2 + stage.edge_count
    )


@pytest.mark.parametrize(
    "changed", ["source", "pointer", "history", "candidate", "seal", "sibling"]
)
def test_voting_publication_refuses_drift_before_pointer_write(
    voting_promotion: VotingPromotionFixture,
    changed: str,
) -> None:
    fixture = voting_promotion.repair.fixture
    voting_promotion.stage()
    voting_promotion.accept()
    if changed == "seal":
        with (voting_promotion.output / BundleFile.STAGED_DOCUMENTS).open(
            "a"
        ) as handle:
            handle.write("\n")
    elif changed == "sibling":
        sibling = GraphVersionPointer(signal=Signal.TOPIC, graph_version="concurrent")
        fixture.source.index(
            index=fixture.graph_index,
            id=sibling.id,
            document=sibling.model_dump(mode="json"),
            refresh=True,
        )
    else:
        if changed == "source":
            index = fixture.source_index
            identity, body = next(iter(fixture.documents().items()))
        else:
            index = fixture.graph_index
            if changed == "pointer":
                identity = RecordId(fixture.pointer.id)
            elif changed == "history":
                identity = RecordId(voting_promotion.repair.edge.id)
            else:
                identity = next(
                    RepairBundle(voting_promotion.output).rows(
                        BundleFile.STAGED_DOCUMENTS, StoredDocument
                    )
                ).id
            body = fixture.source.get(index=index, id=identity)["_source"]
        fixture.source.index(index=index, id=identity, document=body, refresh=True)
    with patch.object(fixture.source, "index") as write, pytest.raises(ValueError):
        voting_promotion.publish()
    write.assert_not_called()
    assert not (voting_promotion.output / BundleFile.PROMOTION_STARTED).exists()


def test_voting_publication_requires_bound_serving_acceptance(
    voting_promotion: VotingPromotionFixture,
) -> None:
    voting_promotion.stage()
    with pytest.raises(ValueError, match="Missing or unsafe"):
        voting_promotion.publish()
    voting_promotion.accept()
    acceptance = VotingServingAcceptance.model_validate_json(
        (voting_promotion.output / BundleFile.SERVING_ACCEPTANCE).read_text()
    )
    acceptance.member = "not-the-tested-member"
    (voting_promotion.output / BundleFile.SERVING_ACCEPTANCE).unlink()
    RepairBundle(voting_promotion.output).write(
        BundleFile.SERVING_ACCEPTANCE, acceptance
    )
    with pytest.raises(ValueError, match="not bound"):
        voting_promotion.publish()


def test_voting_staging_refuses_existing_candidate_without_overwrite(
    voting_promotion: VotingPromotionFixture,
) -> None:
    fixture = voting_promotion.repair.fixture
    edge = next(
        RepairBundle(voting_promotion.repair.accepted).rows(
            BundleFile.EDGES, MemberEdge
        )
    )
    fixture.source.index(
        index=fixture.graph_index,
        id=edge.id,
        document=edge.model_dump(mode="json"),
        refresh=True,
    )
    before = fixture.source.get(index=fixture.graph_index, id=edge.id).body
    with pytest.raises(ValueError, match="already exists"):
        voting_promotion.stage()
    assert fixture.source.get(index=fixture.graph_index, id=edge.id).body == before
    assert not voting_promotion.output.exists()


@pytest.mark.parametrize("changed", ["version", "viewport", "checksum"])
def test_voting_publication_rejects_unproven_browser_or_api_evidence(
    voting_promotion: VotingPromotionFixture,
    changed: str,
) -> None:
    voting_promotion.stage()
    voting_promotion.accept()
    browser_path = voting_promotion.output / BundleFile.SERVING_BROWSER
    if changed == "checksum":
        with browser_path.open("a") as handle:
            handle.write("\n")
    else:
        report = BrowserAcceptance.model_validate_json(browser_path.read_text())
        case = report.suites[0].specs[1].tests[0]
        if changed == "viewport":
            case.project = BrowserViewport.DESKTOP
        else:
            graph = NeighborhoodResponse.model_validate_json(
                b64decode(case.results[0].attachments[0].body or "", validate=True)
            )
            graph.versions[Signal.VOTING] = "not-the-tested-stage"
            case.results[0].attachments[0].body = b64encode(
                graph.model_dump_json().encode()
            ).decode()
        browser_path.unlink()
        RepairBundle(voting_promotion.output).write(BundleFile.SERVING_BROWSER, report)
        path = voting_promotion.output / BundleFile.SERVING_ACCEPTANCE
        acceptance = VotingServingAcceptance.model_validate_json(path.read_text())
        acceptance.browser_report = FileSeal.read(browser_path)
        path.unlink()
        RepairBundle(voting_promotion.output).write(
            BundleFile.SERVING_ACCEPTANCE, acceptance
        )
    with (
        patch.object(voting_promotion.tool.client, "index") as write,
        pytest.raises(ValueError),
    ):
        voting_promotion.publish()
    write.assert_not_called()


@pytest.mark.parametrize("response_lost", [False, True])
def test_voting_pointer_failure_never_claims_success_or_unknown_rollback_ownership(
    voting_promotion: VotingPromotionFixture,
    response_lost: bool,
) -> None:
    fixture = voting_promotion.repair.fixture
    voting_promotion.stage()
    voting_promotion.accept()
    write = fixture.source.index

    def fail_write(
        *,
        index: str,
        id: str,
        document: JsonObject,
        if_seq_no: int,
        if_primary_term: int,
        refresh: bool,
    ) -> ObjectApiResponse[JsonObject]:
        if response_lost:
            write(
                index=index,
                id=id,
                document=document,
                if_seq_no=if_seq_no,
                if_primary_term=if_primary_term,
                refresh=refresh,
            )
        raise RuntimeError("injected pointer response failure")

    with (
        patch.object(fixture.source, "index", side_effect=fail_write),
        pytest.raises(RuntimeError, match="injected"),
    ):
        voting_promotion.publish()
    assert not (voting_promotion.output / BundleFile.PROMOTED).exists()
    assert not (voting_promotion.output / BundleFile.PROMOTION_RECEIPT).exists()
    with pytest.raises(ValueError):
        voting_promotion.publish(rollback=True)


def test_voting_pointer_cas_rejects_race_after_complete_preflight(
    voting_promotion: VotingPromotionFixture,
) -> None:
    fixture = voting_promotion.repair.fixture
    voting_promotion.stage()
    voting_promotion.accept()
    write = fixture.source.index
    concurrent = fixture.pointer.model_copy(
        update={"graph_version": "concurrent"}
    ).model_dump(mode="json")

    def race(
        *,
        index: str,
        id: str,
        document: JsonObject,
        if_seq_no: int,
        if_primary_term: int,
        refresh: bool,
    ) -> ObjectApiResponse[JsonObject]:
        write(index=index, id=id, document=concurrent, refresh=True)
        return write(
            index=index,
            id=id,
            document=document,
            if_seq_no=if_seq_no,
            if_primary_term=if_primary_term,
            refresh=refresh,
        )

    with (
        patch.object(fixture.source, "index", side_effect=race),
        pytest.raises(ConflictError),
    ):
        voting_promotion.publish()
    assert (
        fixture.source.get(index=fixture.graph_index, id=fixture.pointer.id)["_source"]
        == concurrent
    )
    assert not (voting_promotion.output / BundleFile.PROMOTION_RECEIPT).exists()
    assert not (voting_promotion.output / BundleFile.PROMOTED).exists()


def test_partial_voting_stage_never_changes_pointer_or_claims_readiness(
    voting_promotion: VotingPromotionFixture,
) -> None:
    fixture = voting_promotion.repair.fixture
    before = fixture.source.get(index=fixture.graph_index, id=fixture.pointer.id).body

    def partial_write(
        client: Elasticsearch, actions: Iterator[JsonObject], **_options: bool
    ) -> tuple[int, list[JsonObject]]:
        edge = MemberEdge.model_validate(next(actions)["_source"])
        client.create(
            index=fixture.graph_index, id=edge.id, document=edge.model_dump(mode="json")
        )
        raise RuntimeError("injected partial voting stage")

    with (
        patch("cdm.graph.promotion.bulk", side_effect=partial_write),
        pytest.raises(RuntimeError, match="partial"),
    ):
        voting_promotion.stage()
    assert (
        fixture.source.get(index=fixture.graph_index, id=fixture.pointer.id).body
        == before
    )
    assert not (voting_promotion.output / BundleFile.STAGED).exists()
    fixture.source.indices.refresh(index=fixture.graph_index)
    assert fixture.source.count(index=fixture.graph_index)["count"] == 3


def test_bounded_live_repair_and_rollback_preserve_graph_and_unrelated_sources(
    live_repair: LiveRepairFixture,
) -> None:
    fixture = live_repair.fixture
    before = fixture.documents()
    live_repair.prepare()
    result = live_repair.tool.apply(live_repair.root, live_repair.output)
    assert result.records == 2
    assert len(result.mapping_paths) == 8
    assert fixture.documents() != before
    assert fixture.source.get(index=fixture.graph_index, id=live_repair.edge.id)[
        "_source"
    ] == live_repair.edge.model_dump(mode="json")
    assert (
        fixture.source.count(
            index=fixture.graph_index, query={"term": {"shared_votes": 7}}
        )["count"]
        == 0
    )
    restored = live_repair.tool.rollback(live_repair.root, live_repair.output)
    assert restored.records == 2
    assert fixture.documents() == before
    assert (
        fixture.source.indices.get_mapping(index=fixture.graph_index)[
            fixture.graph_index
        ]["mappings"]["properties"]["shared_votes"]["type"]
        == "integer"
    )
    assert fixture.source.get(index=fixture.graph_index, id=fixture.pointer.id)[
        "_source"
    ] == fixture.pointer.model_dump(mode="json")


def test_live_repair_refuses_stale_source_before_mapping_write(
    live_repair: LiveRepairFixture,
) -> None:
    fixture = live_repair.fixture
    live_repair.prepare()
    document = next(iter(fixture.documents().items()))
    fixture.source.index(
        index=fixture.source_index, id=document[0], document=document[1], refresh=True
    )
    with (
        patch.object(fixture.source.indices, "put_mapping") as mapping,
        pytest.raises(ValueError, match="Source preconditions changed"),
    ):
        live_repair.tool.apply(live_repair.root, live_repair.output)
    mapping.assert_not_called()
    assert not (live_repair.output / BundleFile.STARTED).exists()


def test_live_repair_refuses_pointer_drift_before_mapping_write(
    live_repair: LiveRepairFixture,
) -> None:
    fixture = live_repair.fixture
    live_repair.prepare()
    fixture.source.index(
        index=fixture.graph_index,
        id=fixture.pointer.id,
        document=fixture.pointer.model_copy(
            update={"graph_version": "concurrent"}
        ).model_dump(mode="json"),
    )
    with (
        patch.object(fixture.source.indices, "put_mapping") as mapping,
        pytest.raises(ValueError, match="preconditions changed"),
    ):
        live_repair.tool.apply(live_repair.root, live_repair.output)
    mapping.assert_not_called()


def test_live_repair_refuses_changed_backup(live_repair: LiveRepairFixture) -> None:
    live_repair.prepare()
    with (live_repair.output / BundleFile.GRAPH_BACKUP).open("a") as handle:
        handle.write("\n")
    with pytest.raises(ValueError, match="evidence changed"):
        live_repair.tool.apply(live_repair.root, live_repair.output)
    assert not (live_repair.output / BundleFile.STARTED).exists()


@pytest.mark.parametrize("response_lost", [False, True])
def test_failed_repair_has_no_success_and_preserves_rollback_safety(
    live_repair: LiveRepairFixture,
    response_lost: bool,
) -> None:
    fixture = live_repair.fixture
    before = fixture.documents()
    live_repair.prepare()
    write = fixture.source.index
    calls = 0

    def fail_write(
        *,
        index: str,
        id: str,
        document: JsonObject,
        if_seq_no: int,
        if_primary_term: int,
    ) -> ObjectApiResponse[JsonObject]:
        nonlocal calls
        calls += 1
        if response_lost:
            write(
                index=index,
                id=id,
                document=document,
                if_seq_no=if_seq_no,
                if_primary_term=if_primary_term,
            )
            raise RuntimeError("injected response loss")
        if calls > 1:
            raise RuntimeError("injected write failure")
        return write(
            index=index,
            id=id,
            document=document,
            if_seq_no=if_seq_no,
            if_primary_term=if_primary_term,
        )

    with (
        patch.object(fixture.source, "index", side_effect=fail_write),
        pytest.raises(RuntimeError, match="injected"),
    ):
        live_repair.tool.apply(live_repair.root, live_repair.output)
    assert not (live_repair.output / BundleFile.APPLIED).exists()
    if response_lost:
        with pytest.raises(ValueError, match="indeterminate source write"):
            live_repair.tool.rollback(live_repair.root, live_repair.output)
        assert not (live_repair.output / BundleFile.ROLLED_BACK).exists()
    else:
        assert (
            live_repair.tool.rollback(live_repair.root, live_repair.output).records == 1
        )
        assert fixture.documents() == before


def test_live_rollback_refuses_concurrent_source_change(
    live_repair: LiveRepairFixture,
) -> None:
    fixture = live_repair.fixture
    live_repair.prepare()
    live_repair.tool.apply(live_repair.root, live_repair.output)
    identity = "rollcall:114:house:1"
    document = StoredDocument.model_validate(
        fixture.source.get(index=fixture.source_index, id=identity).body
    )
    fixture.source.index(
        index=fixture.source_index, id=identity, document=document.source, refresh=True
    )
    with pytest.raises(ValueError, match="Concurrent/indeterminate"):
        live_repair.tool.rollback(live_repair.root, live_repair.output)
    assert not (live_repair.output / BundleFile.ROLLED_BACK).exists()


def test_backup_restore_rejects_serving_cluster(live_repair: LiveRepairFixture) -> None:
    fixture = live_repair.fixture
    tool = LiveGraphRepair(fixture.capture, GraphRepairRehearsal(fixture.source))
    with (
        patch.object(fixture.source.indices, "create") as create,
        pytest.raises(ValueError, match="different cluster UUID"),
    ):
        tool.prepare(live_repair.root, live_repair.accepted, live_repair.output)
    create.assert_not_called()
    assert not (live_repair.output / BundleFile.PREPARED).exists()


@pytest.mark.parametrize("response_lost", [False, True])
def test_interrupted_rollback_resumes_only_receipted_writes(
    live_repair: LiveRepairFixture,
    response_lost: bool,
) -> None:
    fixture = live_repair.fixture
    before = fixture.documents()
    live_repair.prepare()
    live_repair.tool.apply(live_repair.root, live_repair.output)
    write = fixture.source.index
    calls = 0

    def interrupted(
        *,
        index: str,
        id: str,
        document: JsonObject,
        if_seq_no: int,
        if_primary_term: int,
    ) -> ObjectApiResponse[JsonObject]:
        nonlocal calls
        calls += 1
        if response_lost:
            write(
                index=index,
                id=id,
                document=document,
                if_seq_no=if_seq_no,
                if_primary_term=if_primary_term,
            )
            raise RuntimeError("injected rollback response loss")
        if calls > 1:
            raise RuntimeError("injected rollback failure")
        return write(
            index=index,
            id=id,
            document=document,
            if_seq_no=if_seq_no,
            if_primary_term=if_primary_term,
        )

    with (
        patch.object(fixture.source, "index", side_effect=interrupted),
        pytest.raises(RuntimeError, match="injected rollback"),
    ):
        live_repair.tool.rollback(live_repair.root, live_repair.output)
    assert not (live_repair.output / BundleFile.ROLLED_BACK).exists()
    if response_lost:
        with pytest.raises(ValueError, match="indeterminate source write"):
            live_repair.tool.rollback(live_repair.root, live_repair.output)
    else:
        assert (
            live_repair.tool.rollback(live_repair.root, live_repair.output).records == 2
        )
        assert fixture.documents() == before


def test_graph_backup_bound_is_checked_before_capture(repair: RepairFixture) -> None:
    repair.capture.config = repair.config.model_copy(update={"max_graph_records": 1})
    fixture = LiveRepairFixture(repair)
    with pytest.raises(ValueError, match="approved record bound"):
        fixture.prepare()
    assert not fixture.output.exists()

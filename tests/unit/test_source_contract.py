import sys
from datetime import UTC, datetime, timedelta
from itertools import permutations
from pathlib import Path
from unittest.mock import Mock, PropertyMock

import pytest
import requests
from elasticsearch import Elasticsearch
from redis import Redis

from cdm.config.app_config import RedisConfig
from cdm.config.source_policy import SourceName, SourcePolicy
from cdm.ingest.archive import SQLiteRecordArchive
from cdm.ingest.govinfo import (
    GovInfoBillStatusParser,
    GovInfoDownloader,
    GovInfoManifestStore,
    GovInfoPackage,
)
from cdm.ingest.reconciliation import (
    BillReconciler,
    TargetInventory,
    replay_govinfo_archives,
)
from cdm.ingest.source_contract import (
    CoverageState,
    ExpectationKind,
    FreshnessState,
    ResourceCoverage,
    StageCoverage,
)
from cdm.jobs.payloads import GovInfoPackagePayload, IndexPayload
from cdm.jobs.store import JobStore
from cdm.utils.json_types import JsonObject
from cdm.utils.rate_limiter import TokenBucket
from cdm.workers.dispatch import JobDispatcher, JobSubmitter
from cdm.workers.govinfo_runner import GovInfoPackageRunner
from scripts.reconcile_govinfo_bulk import main


class SourceFixture:
    @staticmethod
    def record(
        version: str | None, actions: list[str] | None = None, *, complete: bool = True
    ) -> JsonObject:
        record: JsonObject = {
            "id": "bill:119:hr:1",
            "congress": 119,
            "type": "hr",
            "number": "1",
            "title": "Title",
            "source_metadata": {"source": SourceName.BILLSTATUS},
        }
        if actions is not None:
            record["actions"] = actions
        if version is not None:
            record["source_snapshot"] = {
                "source": SourceName.BILLSTATUS,
                "version": version,
                "complete_fields": ["actions"]
                if complete and actions is not None
                else [],
            }
        return record

    @staticmethod
    def client(target: str = "shadow", *, alias: bool = False) -> Mock:
        client = Mock(spec=Elasticsearch, indices=Mock())
        client.indices.get_alias.return_value.body = {
            target: {"aliases": {"live-read": {}} if alias else {}},
        }
        client.indices.get_mapping.return_value.body = {
            target: {"mappings": {"properties": {"id": {"type": "keyword"}}}},
        }
        client.count.return_value.body = {"count": 0}
        return client


class TestGovInfoSnapshotRetention:
    def test_reparse_retains_versions_and_pins_each_index_job_to_its_snapshot(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        artifact = tmp_path / "source.xml"
        root = tmp_path / "archives"
        payload = GovInfoPackagePayload(
            package_id="BILLSTATUS-119hr1",
            collection="BILLSTATUS",
            congress=119,
            measure_type="hr",
            url="https://example.invalid/status.xml",
            outdir=str(root),
        )
        store = Mock(spec=JobStore)
        store.mark_running.side_effect = [
            {"payload": payload.to_json(), "attempts": attempt} for attempt in (1, 2, 3)
        ]
        submitter = Mock(spec=JobSubmitter)
        submitter.submit.return_value = {"id": "index:test"}
        downloader = Mock(return_value=artifact)
        monkeypatch.setattr(GovInfoDownloader, "download", downloader)
        monkeypatch.setattr(
            GovInfoManifestStore,
            "get",
            Mock(
                side_effect=[
                    {"fetched_at": "2026-01-02T00:00:00Z"},
                    {"fetched_at": "2026-01-03T00:00:00Z"},
                    {"fetched_at": "2026-01-03T00:00:00Z"},
                ]
            ),
        )
        runner = GovInfoPackageRunner(
            store,
            Mock(spec=Redis),
            submitter,
            Mock(spec=JobDispatcher),
            RedisConfig(),
            Mock(spec=requests.Session),
            Mock(spec=TokenBucket),
        )
        roots: list[Path] = []
        records: list[JsonObject] = []
        first_bytes = b""
        for day in (1, 2, 2):
            artifact.write_text(
                f"<billStatus><bill><updateDate>2026-01-0{day}T00:00:00Z</updateDate>"
                f"<title>Title {day}</title><actions/></bill></billStatus>"
            )
            runner.run("govinfo_bulk:test")
            index = IndexPayload.model_validate(submitter.submit.call_args.args[1])
            assert index.archive_root is not None
            snapshot_root = Path(index.archive_root)
            roots.append(snapshot_root)
            archive = SQLiteRecordArchive(snapshot_root, 1, read_only=True)
            records.extend(archive.records("bill"))
            archive.engine.dispose()
            if not first_bytes:
                first_bytes = (snapshot_root / "records.sqlite3").read_bytes()
        assert roots[0] != roots[1]
        assert roots[1] == roots[2]
        assert (roots[0] / "records.sqlite3").read_bytes() == first_bytes
        assert len(list(root.glob("*/records.sqlite3"))) == 2
        result = BillReconciler(SourcePolicy()).reconcile(records)
        assert result.records[0]["title"] == "Title 2"
        metadata = result.records[0]["source_metadata"]
        assert isinstance(metadata, list)
        assert len(metadata) == 2

    def test_staging_write_rejects_preview_limit_before_building_clients(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        container = Mock()
        monkeypatch.setattr("scripts.reconcile_govinfo_bulk.WorkerContainer", container)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "reconcile",
                "--archive-root",
                "archives",
                "--target-index",
                "shadow",
                "--write-staging",
                "--max-records",
                "100",
            ],
        )
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 2
        container.assert_not_called()


class TestSourceAuthority:
    @pytest.mark.parametrize("location", ["record", "snapshot"])
    def test_source_version_cannot_postdate_its_source_check(
        self, location: str
    ) -> None:
        record = SourceFixture.record("2026-01-01T00:00:00Z", [])
        if location == "record":
            record["source_checked_at"] = "2025-01-01T00:00:00Z"
        else:
            snapshot = record["source_snapshot"]
            assert isinstance(snapshot, dict)
            snapshot["checked_at"] = "2025-01-01T00:00:00Z"
        with pytest.raises(ValueError, match="postdates"):
            BillReconciler(SourcePolicy()).reconcile([record])

    def test_billstatus_producer_certifies_present_containers_not_missing_ones(
        self,
    ) -> None:
        package = GovInfoPackage(
            package_id="BILLSTATUS-119hr1",
            collection="BILLSTATUS",
            congress=119,
            measure_type="hr",
            url="https://example.invalid/status.xml",
        )
        xml = "<billStatus><bill><updateDate>2026-01-02T00:00:00Z</updateDate><title>Corrected</title><actions/></bill></billStatus>"
        record = GovInfoBillStatusParser().parse(xml, package)
        candidate = BillReconciler(SourcePolicy()).candidate(record)
        assert candidate.snapshot is not None
        assert set(candidate.snapshot.complete_fields) == {
            "title",
            "actions",
            "latest_action",
        }
        missing_version = GovInfoBillStatusParser().parse(
            xml.replace("<updateDate>2026-01-02T00:00:00Z</updateDate>", ""), package
        )
        assert "source_snapshot" not in missing_version
        assert missing_version["source_snapshot_unavailable_reason"]
        text_update = GovInfoBillStatusParser().parse(
            xml.replace(
                "<title>",
                "<updateDateIncludingText>2026-01-03T00:00:00Z</updateDateIncludingText><title>",
            ),
            package,
        )
        candidate = BillReconciler(SourcePolicy()).candidate(text_update)
        assert candidate.snapshot is not None and candidate.snapshot.version.day == 3

    @pytest.mark.parametrize("new_actions", [[], ["corrected"]])
    def test_newer_complete_fields_remove_or_correct_without_arrival_order(
        self,
        new_actions: list[str],
    ) -> None:
        records = [
            SourceFixture.record("2026-01-01T00:00:00Z", ["removed"]),
            SourceFixture.record("2026-01-02T00:00:00Z", new_actions),
            SourceFixture.record(None, ["unverified-old"]),
        ]
        reconciler = BillReconciler(SourcePolicy())
        results = [
            reconciler.reconcile(order).model_dump(mode="json")
            for order in permutations(records)
        ]
        assert all(result == results[0] for result in results)
        assert results[0]["records"][0]["actions"] == new_actions

    @pytest.mark.parametrize("actions", [None, []])
    def test_sparse_newer_record_cannot_erase_a_proven_field(
        self, actions: list[str] | None
    ) -> None:
        result = BillReconciler(SourcePolicy()).reconcile(
            [
                SourceFixture.record("2026-01-01T00:00:00Z", ["retained"]),
                SourceFixture.record("2026-01-02T00:00:00Z", actions, complete=False),
            ]
        )
        assert result.records[0]["actions"] == ["retained"]

    def test_equal_verified_version_with_conflicting_data_blocks_replay(self) -> None:
        with pytest.raises(ValueError, match="Equal-version source conflict"):
            BillReconciler(SourcePolicy()).reconcile(
                [
                    SourceFixture.record("2026-01-01T00:00:00Z", ["a"]),
                    SourceFixture.record("2026-01-01T00:00:00Z", ["b"]),
                ]
            )

    def test_equal_version_same_data_is_idempotent(self) -> None:
        record = SourceFixture.record("2026-01-01T00:00:00Z", ["a"])
        assert BillReconciler(SourcePolicy()).reconcile([record, record]).records[0][
            "actions"
        ] == ["a"]

    @pytest.mark.parametrize(
        "field,value", [("congress", 118), ("type", "s"), ("number", "2")]
    )
    def test_canonical_identity_disagreement_is_rejected(
        self, field: str, value: str | int
    ) -> None:
        record = SourceFixture.record(None)
        record[field] = value
        with pytest.raises(ValueError, match="identity collision"):
            BillReconciler(SourcePolicy()).reconcile([record])

    def test_date_suffixed_identity_does_not_hide_distinct_introductions(self) -> None:
        first = SourceFixture.record(None)
        second = SourceFixture.record(None)
        first.update(id="bill:119:hr:1:2025-01-01", introduced_date="2025-01-01")
        second.update(id="bill:119:hr:1:2025-02-01", introduced_date="2025-02-01")
        with pytest.raises(ValueError, match="identity collision"):
            BillReconciler(SourcePolicy()).reconcile([first, second])

    def test_unproven_records_are_not_reported_as_complete(self) -> None:
        result = BillReconciler(SourcePolicy()).reconcile([SourceFixture.record(None)])
        evidence = result.records[0]["reconciliation"]
        assert isinstance(evidence, dict) and evidence["status"] == "partial"


class TestCoverageEvidence:
    @pytest.mark.parametrize(
        "kind", [ExpectationKind.UNKNOWN, ExpectationKind.ESTIMATED]
    )
    def test_equal_counts_without_authoritative_evidence_are_partial(
        self, kind: ExpectationKind
    ) -> None:
        stage = StageCoverage(
            observed=10,
            expected=10,
            expectation=kind,
            identities_verified=True,
            reason="fixture",
        )
        assert stage.state == CoverageState.PARTIAL

    def test_verified_zero_and_distinct_counts_can_be_complete(self) -> None:
        for count in (0, 10):
            stage = StageCoverage(
                observed=count,
                expected=count,
                expectation=ExpectationKind.AUTHORITATIVE,
                identities_verified=True,
                reason="upstream inventory fixture",
            )
            assert stage.state == CoverageState.COMPLETE
            assert (
                stage.model_copy(update={"observed": count + 1}).state
                == CoverageState.PARTIAL
            )
            assert (
                stage.model_copy(update={"identities_verified": False}).state
                == CoverageState.PARTIAL
            )

    @pytest.mark.parametrize("disposition", ["failed", "unavailable", "not_applicable"])
    def test_dispositions_require_explicit_reasons(self, disposition: str) -> None:
        stage = StageCoverage.model_validate(
            {disposition: True, "reason": "verified provider limitation"}
        )
        assert stage.state.value == disposition
        with pytest.raises(ValueError):
            StageCoverage.model_validate({disposition: True, "reason": ""})

    @pytest.mark.parametrize(
        "hours,expected", [(24, FreshnessState.FRESH), (24.01, FreshnessState.STALE)]
    )
    def test_exact_freshness_boundary_is_last_source_check_not_publication(
        self,
        hours: float,
        expected: FreshnessState,
    ) -> None:
        now = datetime(2026, 11, 2, tzinfo=UTC)
        stage = StageCoverage(reason="unknown upstream inventory")
        coverage = ResourceCoverage(
            resource="bill",
            congress=119,
            discovery=stage,
            hydration=stage,
            indexing=stage,
            assessed_at=now,
            checked_at=now - timedelta(hours=hours),
        )
        coverage.assess_freshness(SourcePolicy())
        assert coverage.freshness == expected


class TestShadowSafety:
    def test_one_fresh_contributor_cannot_hide_a_stale_source(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "archives"
        archive = SQLiteRecordArchive(root / "package", 0)
        for source, hours in [(SourceName.BILLSTATUS, 25), (SourceName.BILLSUM, 1)]:
            record = SourceFixture.record(None)
            record["source_metadata"] = {"source": source}
            record["source_checked_at"] = (
                datetime.now(UTC) - timedelta(hours=hours)
            ).isoformat()
            archive.write("bill", record, record_id=source)
        archive.engine.dispose()
        report = replay_govinfo_archives(
            root,
            None,
            target_index=None,
            report_path=tmp_path / "report.json",
            preview=True,
            max_records=2,
        )
        coverage = report["coverage"]
        assert isinstance(coverage, list) and isinstance(coverage[0], dict)
        assert coverage[0]["freshness"] == "stale"

    def test_source_check_freshness_does_not_require_a_comparable_record_version(
        self,
        tmp_path: Path,
    ) -> None:
        root = tmp_path / "archives"
        archive = SQLiteRecordArchive(root / "package", 0)
        record = SourceFixture.record(None)
        record["source_checked_at"] = datetime.now(UTC).isoformat()
        archive.write("bill", record)
        archive.engine.dispose()
        report = replay_govinfo_archives(
            root,
            None,
            target_index=None,
            report_path=tmp_path / "report.json",
            preview=True,
            max_records=1,
        )
        coverage = report["coverage"]
        assert isinstance(coverage, list) and isinstance(coverage[0], dict)
        assert coverage[0]["freshness"] == "fresh"
        assert report["source_coverage"] == "partial"

    def test_archives_only_cli_never_constructs_a_search_client(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path / "archives"
        archive = SQLiteRecordArchive(root / "package", 0)
        archive.engine.dispose()
        container = Mock()
        client = PropertyMock(
            side_effect=AssertionError("Search access in archive-only mode")
        )
        monkeypatch.setattr(type(container), "elastic_client", client, raising=False)
        monkeypatch.setattr(
            "scripts.reconcile_govinfo_bulk.WorkerContainer",
            Mock(return_value=container),
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "reconcile",
                "--archive-root",
                str(root),
                "--archives-only",
                "--report-path",
                str(tmp_path / "report.json"),
            ],
        )
        main()
        client.assert_not_called()
        container.job_submitter.submit.assert_not_called()

    @pytest.mark.parametrize(
        "extra", [("--target-index", "shadow"), ("--write-staging",)]
    )
    def test_archives_only_cannot_be_combined_with_a_write_or_target(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        extra: tuple[str, ...],
    ) -> None:
        factory = Mock()
        monkeypatch.setattr("scripts.reconcile_govinfo_bulk.WorkerContainer", factory)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "reconcile",
                "--archive-root",
                str(tmp_path),
                "--archives-only",
                "--report-path",
                str(tmp_path / "report.json"),
                *extra,
            ],
        )
        with pytest.raises(SystemExit) as error:
            main()
        assert error.value.code == 2
        factory.assert_not_called()

    @pytest.mark.parametrize(
        "hours,expected", [(1, "fresh"), (25, "stale"), (None, "unknown")]
    )
    def test_preview_freshness_uses_http_check_age_not_old_source_version(
        self,
        tmp_path: Path,
        hours: int | None,
        expected: str,
    ) -> None:
        root = tmp_path / "archives"
        archive = SQLiteRecordArchive(root / "package", 0)
        record = SourceFixture.record("2025-01-01T00:00:00Z", [])
        snapshot = record["source_snapshot"]
        assert isinstance(snapshot, dict)
        if hours is not None:
            snapshot["checked_at"] = (
                datetime.now(UTC) - timedelta(hours=hours)
            ).isoformat()
        archive.write("bill", record)
        archive.engine.dispose()
        report = replay_govinfo_archives(
            root,
            SourceFixture.client(),
            target_index="shadow",
            report_path=tmp_path / "report.json",
            preview=True,
            max_records=1,
        )
        coverage = report["coverage"]
        assert isinstance(coverage, list) and isinstance(coverage[0], dict)
        assert coverage[0]["freshness"] == expected

    def test_preview_reports_collisions_without_mutating_or_discarding_sources(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "archives"
        archive = SQLiteRecordArchive(root / "package", 0)
        for value in ("a", "b"):
            archive.write(
                "bill",
                SourceFixture.record("2026-01-01T00:00:00Z", [value]),
                record_id=value,
            )
        archive.engine.dispose()
        before = archive.path.read_bytes()
        report = replay_govinfo_archives(
            root,
            SourceFixture.client(),
            target_index="shadow",
            report_path=tmp_path / "report.json",
            preview=True,
            max_records=10,
        )
        assert report["parent_count"] == 0 and report["quarantine_count"] == 1
        assert report["promotable"] is False
        assert archive.path.read_bytes() == before

    def test_default_cli_never_submits_a_job(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path / "archives"
        archive = SQLiteRecordArchive(root / "package", 0)
        archive.write("bill", SourceFixture.record(None))
        archive.engine.dispose()
        container = Mock(elastic_client=SourceFixture.client())
        monkeypatch.setattr(
            "scripts.reconcile_govinfo_bulk.WorkerContainer",
            Mock(return_value=container),
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "reconcile",
                "--archive-root",
                str(root),
                "--target-index",
                "shadow",
                "--report-path",
                str(tmp_path / "report.json"),
            ],
        )
        main()
        container.job_submitter.submit.assert_not_called()
        container.elastic_client.bulk.assert_not_called()
        assert (tmp_path / "report.json").is_file()

    def test_write_cli_requires_explicit_flag(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        container = Mock()
        container.job_submitter.submit.return_value = {
            "id": "staging-job",
            "status": "queued",
        }
        monkeypatch.setattr(
            "scripts.reconcile_govinfo_bulk.WorkerContainer",
            Mock(return_value=container),
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "reconcile",
                "--archive-root",
                str(tmp_path),
                "--target-index",
                "shadow",
                "--report-path",
                str(tmp_path / "report.json"),
                "--write-staging",
            ],
        )
        main()
        container.job_submitter.submit.assert_called_once()
        container.elastic_client.bulk.assert_not_called()

    def test_preview_is_bounded_and_does_not_mutate_archive_or_search(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "archives"
        archive = SQLiteRecordArchive(root / "package", 0)
        for number in range(5):
            archive.write("bill", {"id": f"bill:119:hr:{number + 1}", "title": "Title"})
        archive.engine.dispose()
        before = archive.path.read_bytes()
        client = SourceFixture.client(alias=True)
        report = replay_govinfo_archives(
            root,
            client,
            target_index="shadow",
            report_path=tmp_path / "report.json",
            preview=True,
            max_records=2,
        )
        assert report["parent_count"] == 2 and report["status"] == "preview"
        assert report["promotable"] is False
        assert archive.path.read_bytes() == before
        client.bulk.assert_not_called()
        assert client.indices.method_calls == [
            ("exists", (), {"index": "shadow"}),
            ("get_alias", (), {"index": "shadow"}),
            ("get_mapping", (), {"index": "shadow"}),
        ]

    def test_write_refuses_a_live_alias_or_aliased_physical_index(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "archives"
        archive = SQLiteRecordArchive(root / "package", 0)
        archive.engine.dispose()
        client = SourceFixture.client(alias=True)
        with pytest.raises(ValueError, match="unaliased physical staging"):
            replay_govinfo_archives(
                root,
                client,
                target_index="shadow",
                report_path=tmp_path / "report.json",
            )
        client.bulk.assert_not_called()
        inventory = TargetInventory(
            requested="live-read",
            physical_indices=["physical"],
            aliases=[],
            mapped_fields=[],
            existing_documents=0,
        )
        with pytest.raises(ValueError, match="unaliased physical staging"):
            inventory.require_unaliased_staging()

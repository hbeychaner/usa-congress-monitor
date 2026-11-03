import os
from collections.abc import Iterator
from enum import StrEnum
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
from elasticsearch import Elasticsearch

from cdm.backend.services.bill_service import BillService
from cdm.config.source_policy import SourceName
from cdm.contracts.hydration import (
    BillDetailKind,
    DetailEvidence,
    DetailState,
    HydrationAssessment,
    HydrationStatus,
)
from cdm.ingest.archive import SQLiteRecordArchive
from cdm.ingest.govinfo import GovInfoBillStatusParser, GovInfoPackage
from cdm.ingest.reconciliation import replay_govinfo_archives
from cdm.jobs.payloads import IndexPayload
from cdm.store.index_manager import load_definitions
from cdm.store.indexer import to_document
from cdm.store.opensearch import bulk_upsert, read_alias
from cdm.utils.json_types import JsonObject
from cdm.workers.index_runner import ArchiveReplayer


class ProjectionRoute(StrEnum):
    LIVE = "live"
    ARCHIVE = "archive"
    RECONCILIATION = "reconciliation"


class ProjectionFixture:
    def __init__(self, client: Elasticsearch, index: str, archive_root: Path) -> None:
        self.client = client
        self.index = index
        self.archive_root = archive_root
        self.archive = SQLiteRecordArchive(archive_root / "package", 0)
        self.parents: list[JsonObject] = [
            {
                "id": "bill:118:hr:1",
                "congress": 118,
                "type": "hr",
                "number": "1",
                "title": "Versioned text",
            },
            {
                "id": "bill:118:hr:2",
                "congress": 118,
                "type": "hr",
                "number": "2",
                "title": "API text",
                "full_text": "API hydrated text",
            },
        ]
        self.texts: list[JsonObject] = [
            {
                "id": f"bill-text:118:hr:{number}:{version}",
                "congress": 118,
                "type": "hr",
                "number": number,
                "version_code": version,
                "full_text": text,
            }
            for number, version, text in [
                ("1", "ih", "Introduced text"),
                ("1", "enr", "Enrolled text"),
                ("2", "enr", "Must not replace API text"),
            ]
        ]

    @staticmethod
    def lemmas(texts: list[str]) -> list[str]:
        return [f"lemma {text.lower()}" for text in texts]

    def write(self, route: ProjectionRoute, *, reverse: bool = False) -> None:
        texts = list(reversed(self.texts)) if reverse else self.texts
        for resource, records in [("bill", self.parents), ("bill_text", texts)]:
            for record in records:
                self.archive.write(resource, record)

        if route == ProjectionRoute.RECONCILIATION:
            report = replay_govinfo_archives(
                self.archive_root,
                self.client,
                target_index=self.index,
                report_path=self.archive_root / "report.json",
            )
            assert report["quarantine_count"] == 0
            writes = report["write"]
            assert isinstance(writes, dict)
            for family in ("parents", "text_versions"):
                result = writes[family]
                assert isinstance(result, dict)
                assert result["errors"] == 0
        elif route == ProjectionRoute.ARCHIVE:
            replayer = ArchiveReplayer(self.client)
            for resource in ("bill", "bill_text"):
                replayer.replay(
                    IndexPayload(
                        stream="unused",
                        resource=resource,
                        target_index=self.index,
                        archive_root=str(self.archive_root / "package"),
                        batch_size=1,
                    )
                )
        else:
            for resource, records in [("bill", self.parents), ("bill_text", texts)]:
                for record in records:
                    result = bulk_upsert(
                        self.client,
                        resource,
                        [to_document(record, resource)],
                        target_index=self.index,
                    )
                    assert not result["errors"]


class TestSourceSnapshotShadow:
    def test_real_staging_applies_verified_removals_and_corrections(
        self,
        projection: ProjectionFixture,
    ) -> None:
        package = GovInfoPackage(
            package_id="BILLSTATUS-118hr1",
            collection="BILLSTATUS",
            congress=118,
            measure_type="hr",
            url="https://example.invalid/status.xml",
        )
        for day, title, actions in [
            (
                "01",
                "Original",
                "<actions><item><actionDate>2026-01-01</actionDate><text>Removed action</text></item></actions>",
            ),
            ("02", "Corrected", "<actions/>"),
        ]:
            xml = f"<billStatus><bill><updateDate>2026-01-{day}T00:00:00Z</updateDate><title>{title}</title>{actions}</bill></billStatus>"
            record = GovInfoBillStatusParser().parse(xml, package)
            projection.archive.write("bill", record, record_id=day)
        before = projection.archive.path.read_bytes()
        report = replay_govinfo_archives(
            projection.archive_root,
            projection.client,
            target_index=projection.index,
            report_path=projection.archive_root / "report.json",
        )
        source = projection.client.get(index=projection.index, id="bill:118:hr:1")[
            "_source"
        ]
        assert source["title"] == "Corrected" and source["actions"] == []
        assert source["latest_action"] is None
        assert "source_snapshot" not in source
        assert source["reconciliation"]["field_authority"]["actions"][
            "version"
        ].startswith("2026-01-02")
        assert report["source_coverage"] == "partial" and report["promotable"] is False
        assert projection.archive.path.read_bytes() == before

    def test_real_alias_preview_is_read_only_and_write_fails_closed(
        self,
        projection: ProjectionFixture,
    ) -> None:
        projection.archive.write("bill", projection.parents[0])
        alias = f"source-preview-{uuid4().hex}"
        projection.client.indices.put_alias(index=projection.index, name=alias)
        report = replay_govinfo_archives(
            projection.archive_root,
            projection.client,
            target_index=alias,
            report_path=projection.archive_root / "preview.json",
            preview=True,
            max_records=1,
        )
        assert report["status"] == "preview"
        assert projection.client.count(index=projection.index)["count"] == 0
        with pytest.raises(ValueError, match="unaliased physical staging"):
            replay_govinfo_archives(
                projection.archive_root,
                projection.client,
                target_index=projection.index,
                report_path=projection.archive_root / "rejected.json",
            )
        assert not (projection.archive_root / "rejected.json").exists()


@pytest.fixture
def projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[ProjectionFixture]:
    url = os.environ.get("INDEXING_TEST_URL")
    if not url:
        pytest.skip("Set INDEXING_TEST_URL to an isolated Elasticsearch test server")
    client = Elasticsearch(url, request_timeout=30)
    index = f"roadmap-indexing-{uuid4().hex}"
    definition = load_definitions()["legislation"]
    client.indices.create(index=index, **definition)
    monkeypatch.setattr("cdm.store.indexer.lemmatize_texts", ProjectionFixture.lemmas)
    try:
        yield ProjectionFixture(client, index, tmp_path / "archives")
    finally:
        client.indices.delete(index=index, ignore_unavailable=True)
        client.close()


class TestCanonicalProjection:
    def test_hydration_proof_survives_real_updates_without_inheriting_old_claims(
        self, projection: ProjectionFixture
    ) -> None:
        client, index = projection.client, projection.index
        client.indices.put_alias(index=index, name=read_alias("bill"))
        service = BillService(client, Mock())
        bill_id = "bill:118:hr:1"
        client.index(
            index=index,
            id=bill_id,
            document={
                "id": bill_id,
                "source_type": "bill",
                "title": "Retained title",
                "full_text": "Retained body",
                "hydration_status": "complete",
            },
        )
        assert service.get(bill_id).bill.hydration.status is HydrationStatus.UNKNOWN
        assessment = HydrationAssessment.assess(
            {
                kind: DetailEvidence(
                    page_count=1,
                    expected_count=0,
                    fetched_count=0,
                    state=DetailState.OBJECT
                    if kind is BillDetailKind.SUBJECTS
                    else DetailState.EXPANDED,
                    complete=True,
                    reason="Verified empty response.",
                )
                for kind in BillDetailKind
            }
        )
        for expected, proof in [
            (HydrationStatus.COMPLETE, assessment),
            (
                HydrationStatus.UNKNOWN,
                HydrationAssessment(source=SourceName.BILLSTATUS),
            ),
        ]:
            document = to_document(
                {
                    "id": bill_id,
                    "hydration_assessment": proof.model_dump(mode="json"),
                },
                "bill",
            )
            bulk_upsert(client, "bill", [document], target_index=index)
            stored = client.get(index=index, id=bill_id)["_source"]
            detail = service.get(bill_id).bill
            assert stored["hydration_status"] == expected.value
            assert detail.hydration.status is expected
            assert detail.full_text == "Retained body"
            assert detail.title == "Retained title"
        assert detail.hydration.assessed_at is None
        assert detail.hydration.details == {}

    @pytest.mark.parametrize("route", list(ProjectionRoute))
    @pytest.mark.parametrize("reverse", [False, True])
    def test_text_selection_and_repeated_delivery_match(
        self,
        projection: ProjectionFixture,
        route: ProjectionRoute,
        reverse: bool,
    ) -> None:
        projection.write(route, reverse=reverse)
        projection.write(route, reverse=reverse)
        client, index = projection.client, projection.index
        client.indices.refresh(index=index)

        assert client.count(index=index)["count"] == 2
        first = client.get(index=index, id="bill:118:hr:1")["_source"]
        second = client.get(index=index, id="bill:118:hr:2")["_source"]
        assert first["full_text"] == "Enrolled text"
        assert first["full_text_lemma"] == "lemma enrolled text"
        assert first["full_text_version_rank"] == 3
        assert first["source_type"] == "bill"
        assert second["full_text"] == "API hydrated text"
        assert second["full_text_lemma"] == "lemma api hydrated text"
        assert (
            client.count(index=index, query={"match": {"full_text_lemma": "enrolled"}})[
                "count"
            ]
            == 1
        )

        result = bulk_upsert(
            client,
            "bill",
            [{"id": "bill:118:hr:1", "title": "Sparse refresh"}],
            target_index=index,
        )
        assert not result["errors"]
        refreshed = client.get(index=index, id="bill:118:hr:1")["_source"]
        assert refreshed["full_text"] == first["full_text"]

    @pytest.mark.parametrize("route", list(ProjectionRoute))
    def test_deleted_explicit_target_is_not_recreated(
        self, projection: ProjectionFixture, route: ProjectionRoute
    ) -> None:
        projection.client.indices.delete(index=projection.index)

        with pytest.raises(ValueError, match="Explicit index target"):
            projection.write(route)

        assert not projection.client.indices.exists(index=projection.index)

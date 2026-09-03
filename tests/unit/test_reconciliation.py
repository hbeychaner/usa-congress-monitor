from cdm.ingest.archive import SQLiteRecordArchive
from cdm.ingest.reconciliation import (
    reconcile_bill_sources,
    replay_govinfo_archives,
)


def source(name, package_id):
    return {
        "source": name,
        "collection": name.rsplit(":", 1)[-1].upper(),
        "package_id": package_id,
    }


def test_reconcile_prefers_status_and_preserves_summary_and_provenance():
    result = reconcile_bill_sources([
        {
            "id": "bill:118:hr:1",
            "title": "Official status title",
            "actions": [{"text": "Introduced"}],
            "source_metadata": source("govinfo:billstatus", "BILLSTATUS-118hr1"),
        },
        {
            "id": "bill:118:hr:1",
            "title": "Summary title",
            "summaries": [{"text": "A summary"}],
            "source_metadata": source("govinfo:billsum", "BILLSUM-118hr1"),
        },
    ])

    record = result["records"][0]
    assert record["title"] == "Official status title"
    assert record["actions"] == [{"text": "Introduced"}]
    assert record["summaries"] == [{"text": "A summary"}]
    assert record["source_package_ids"] == [
        "BILLSTATUS-118hr1",
        "BILLSUM-118hr1",
    ]
    assert record["reconciliation"]["status"] == "complete"
    assert record["reconciliation"]["conflicts"][0]["selected_source"] == (
        "govinfo:billstatus"
    )
    assert result["diagnostics"][0]["conflict_count"] == 1


def test_reconcile_unions_lists_and_skips_text_children():
    result = reconcile_bill_sources([
        {
            "id": "bill:118:hr:1",
            "subjects": [{"name": "Health"}],
            "source_metadata": source("govinfo:billstatus", "status"),
        },
        {
            "id": "bill:118:hr:1",
            "subjects": [{"name": "Health"}, {"name": "Labor"}],
            "source_metadata": source("govinfo:billsum", "summary"),
        },
        {"id": "bill-text:118:hr:1:ih", "full_text": "text"},
    ])

    assert result["parent_count"] == 1
    assert result["skipped_count"] == 1
    assert result["records"][0]["subjects"] == [
        {"name": "Health"},
        {"name": "Labor"},
    ]


def test_replay_archives_reconciles_and_writes_parent_and_text_resources(
    tmp_path, monkeypatch
):
    archive_root = tmp_path / "govinfo"
    archive = SQLiteRecordArchive(archive_root / "package-1", 0)
    archive.write(
        "bill",
        {
            "id": "bill:118:hr:1",
            "title": "Status",
            "source_metadata": source("govinfo:billstatus", "status"),
        },
        record_id="status",
    )
    archive.write(
        "bill",
        {
            "id": "bill:118:hr:1",
            "summaries": [{"text": "Summary"}],
            "source_metadata": source("govinfo:billsum", "summary"),
        },
        record_id="summary",
    )
    archive.write(
        "bill_text",
        {
            "id": "bill-text:118:hr:1:ih",
            "full_text": "Section 1",
            "source_metadata": source("govinfo:bills", "text"),
        },
        record_id="text",
    )
    calls = []

    def fake_bulk(client, resource, docs, **kwargs):
        calls.append((resource, docs, kwargs))
        return {"updated": len(docs), "errors": False, "skipped_missing_ids": 0}

    monkeypatch.setattr("cdm.ingest.reconciliation.bulk_upsert", fake_bulk)
    report = replay_govinfo_archives(
        archive_root,
        object(),
        target_index="congress-legislation-v118",
        report_path=tmp_path / "report.json",
    )

    assert report["archive_count"] == 1
    assert report["parent_count"] == 1
    assert report["text_version_count"] == 1
    assert report["document_count"] == 2
    assert [call[0] for call in calls] == ["bill", "bill_text"]
    assert all(
        call[2] == {"target_index": "congress-legislation-v118", "replace": True}
        for call in calls
    )
    assert report["write"]["parents"]["updated"] == 1
    assert report["write"]["text_versions"]["updated"] == 1
    assert (tmp_path / "report.json").exists()


def test_replay_quarantines_invalid_text_documents(tmp_path, monkeypatch):
    archive_root = tmp_path / "govinfo"
    archive = SQLiteRecordArchive(archive_root / "package-1", 0)
    archive.write(
        "bill_text",
        {"full_text": "Missing identity"},
        record_id="invalid-text",
    )
    calls = []

    def fake_bulk(client, resource, docs, **kwargs):
        calls.append((resource, docs, kwargs))
        return {"updated": len(docs), "errors": False, "skipped_missing_ids": 0}

    monkeypatch.setattr("cdm.ingest.reconciliation.bulk_upsert", fake_bulk)
    report = replay_govinfo_archives(
        archive_root,
        object(),
        target_index="congress-legislation-v118",
        report_path=tmp_path / "report.json",
    )

    assert report["quarantine_count"] == 1
    assert report["quarantine"][0]["resource"] == "bill_text"
    assert report["text_version_count"] == 0
    assert [call[0] for call in calls] == ["bill", "bill_text"]
    assert calls[1][1] == []


def test_replay_quarantines_invalid_parent_documents(tmp_path, monkeypatch):
    archive_root = tmp_path / "govinfo"
    archive = SQLiteRecordArchive(archive_root / "package-1", 0)
    archive.write("bill", {"id": "bill:118:hr:1"}, record_id="invalid-bill")
    calls = []

    def fake_bulk(client, resource, docs, **kwargs):
        calls.append((resource, docs, kwargs))
        return {"updated": len(docs), "errors": False, "skipped_missing_ids": 0}

    monkeypatch.setattr("cdm.ingest.reconciliation.bulk_upsert", fake_bulk)

    def reject_parent(document, resource):
        if resource == "bill":
            raise ValueError("invalid parent")
        return document

    monkeypatch.setattr("cdm.ingest.reconciliation.validate_document", reject_parent)
    report = replay_govinfo_archives(
        archive_root,
        object(),
        target_index="congress-legislation-v118",
        report_path=tmp_path / "report.json",
    )

    assert report["reconciled_parent_count"] == 1
    assert report["parent_count"] == 0
    assert report["quarantine_count"] == 1
    assert report["quarantine"][0]["resource"] == "bill"
    assert calls[0][1] == []

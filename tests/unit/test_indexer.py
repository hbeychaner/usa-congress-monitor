from cdm.ingest.archive import SQLiteRecordArchive
from cdm.store.indexer import to_document


def test_to_document_adds_resource_without_mutating_record():
    record = {"id": "congress:118", "name": "118th Congress"}

    document = to_document(record, "congress")

    assert document == {**record, "_resource": "congress"}
    assert record == {"id": "congress:118", "name": "118th Congress"}


def test_to_document_preserves_existing_resource():
    record = {"id": "record:1", "_resource": "custom"}

    assert to_document(record, "amendment")["_resource"] == "custom"


def test_to_document_flattens_bill_member_relationships():
    document = to_document(
        {
            "id": "bill:119:hr:1",
            "sponsors": [{"bioguide_id": "A000001"}],
            "cosponsors": [{"bioguideId": "B000002"}],
        },
        "bill",
    )

    assert document["sponsor_bioguide_ids"] == ["A000001"]
    assert document["cosponsor_bioguide_ids"] == ["B000002"]


def test_to_document_normalizes_reference_id_and_preserves_raw_when_requested():
    record = {
        "id": "bill:118:hr:1",
        "referenceId": "bill:118:hr:1",
        "title": "Example",
    }
    raw_record = {"referenceId": "bill:118:hr:1", "title": "Example"}

    document = to_document(record, "bill", raw_record=raw_record, preserve_raw=True)

    assert document["reference_id"] == "bill:118:hr:1"
    assert "referenceId" not in document
    assert document["_raw"] == raw_record
    assert "referenceId" in record


def test_to_document_copies_ingest_metadata_without_mutating_record():
    record = {"id": "bill:118:hr:1", "title": "Example"}
    ingest_metadata = {
        "hydration_status": "complete",
        "hydrated_sources": ["govinfo:billstatus", "govinfo:bills"],
    }

    document = to_document(record, "bill", ingest_metadata=ingest_metadata)

    assert document["hydration_status"] == "complete"
    assert document["hydrated_sources"] == ["govinfo:billstatus", "govinfo:bills"]
    assert "hydration_status" not in record
    assert "hydrated_sources" not in record


def test_to_document_preserves_bill_detail_hydration_report():
    report = {
        "actions": {
            "page_count": 2,
            "expected_count": 3,
            "fetched_count": 3,
            "state": "complete",
            "complete": True,
        }
    }

    document = to_document({"id": "bill:118:hr:1", "detail_hydration": report}, "bill")

    assert document["detail_hydration"] == report


def test_to_document_extracts_bill_source_provenance():
    document = to_document(
        {
            "id": "bill:118:hr:1",
            "source_metadata": {
                "package_id": "BILLSTATUS-118hr1",
                "url": "https://www.govinfo.gov/status.xml",
            },
        },
        "bill",
    )

    assert document["source_package_ids"] == ["BILLSTATUS-118hr1"]
    assert document["source_urls"] == ["https://www.govinfo.gov/status.xml"]
    assert document["source_metadata"] == [
        {
            "package_id": "BILLSTATUS-118hr1",
            "url": "https://www.govinfo.gov/status.xml",
        }
    ]


def test_to_document_derives_id_from_url():
    document = to_document(
        {"url": "https://api.congress.gov/v3/congress/118?format=json"},
        "congress",
    )

    assert document["id"] == "congress:118"


def test_to_document_rejects_record_without_identity():
    import pytest

    with pytest.raises(ValueError, match="without id or url"):
        to_document({"title": "missing identity"}, "bill")


def test_archive_accepts_source_specific_record_ids(tmp_path):
    archive = SQLiteRecordArchive(tmp_path, 1)

    archive.write("bill", {"id": "bill:118:hr:1"}, record_id="BILLSTATUS-118hr1")
    archive.write("bill", {"id": "bill:118:hr:1"}, record_id="BILLSUM-118hr1")

    assert len(archive.records("bill")) == 2

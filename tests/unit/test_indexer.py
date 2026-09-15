import pytest

import cdm.store.indexer as indexer_module
from cdm.ingest.archive import SQLiteRecordArchive
from cdm.store.indexer import to_document


@pytest.fixture(autouse=True)
def stub_lemmatizer(monkeypatch):
    """Keep unit tests fast and deterministic: no spaCy model loads."""
    monkeypatch.setattr(
        indexer_module, "lemmatize_texts", lambda texts: ["" for _ in texts]
    )


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


def test_to_document_strips_bill_id_date_suffix():
    for suffixed in (
        "bill:119:hr:144:2025-01-03",
        "bill:119:hr:144:2025-01-03T00:00:00",
    ):
        assert to_document({"id": suffixed}, "bill")["id"] == "bill:119:hr:144"
    # non-bill resources and canonical ids untouched
    assert to_document({"id": "bill:119:hr:144"}, "bill")["id"] == "bill:119:hr:144"
    assert (
        to_document({"id": "bill-text:119:hr:144:ih"}, "bill_text")["id"]
        == "bill-text:119:hr:144:ih"
    )


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


def test_to_document_populates_lemma_siblings_for_spec_fields(monkeypatch):
    monkeypatch.setattr(
        indexer_module,
        "lemmatize_texts",
        lambda texts: [f"lemma({text})" for text in texts],
    )

    document = to_document(
        {
            "id": "bill:118:hr:1",
            "title": "Border Acts",
            "latest_action_text": "Referred to committees",
            "full_text": "An Act to secure the border.",
            "summaries": [{"text": "Secures the border."}, {"text": ""}],
        },
        "bill",
    )

    assert document["title_lemma"] == "lemma(Border Acts)"
    assert document["full_text_lemma"] == "lemma(An Act to secure the border.)"
    assert document["summaries"][0]["text_lemma"] == "lemma(Secures the border.)"
    assert "text_lemma" not in document["summaries"][1]
    # Formulaic action strings are keyword territory, not semantic text.
    assert "latest_action_text_lemma" not in document


def test_to_document_skips_lemma_fields_when_lemmatizer_returns_empty():
    document = to_document({"id": "bill:118:hr:1", "title": "Border Acts"}, "bill")

    assert "title_lemma" not in document


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

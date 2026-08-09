from cdm.store.indexer import to_document


def test_to_document_adds_resource_without_mutating_record():
    record = {"id": "congress:118", "name": "118th Congress"}

    document = to_document(record, "congress")

    assert document == {**record, "_resource": "congress"}
    assert record == {"id": "congress:118", "name": "118th Congress"}


def test_to_document_preserves_existing_resource():
    record = {"id": "record:1", "_resource": "custom"}

    assert to_document(record, "amendment")["_resource"] == "custom"


def test_to_document_normalizes_reference_id_and_preserves_raw_when_requested():
    record = {
        "id": "bill:118:hr:1",
        "referenceId": "bill:118:hr:1",
        "title": "Example",
    }
    raw_record = {"referenceId": "bill:118:hr:1", "title": "Example"}

    document = to_document(
        record, "bill", raw_record=raw_record, preserve_raw=True
    )

    assert document["reference_id"] == "bill:118:hr:1"
    assert "referenceId" not in document
    assert document["_raw"] == raw_record
    assert "referenceId" in record


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

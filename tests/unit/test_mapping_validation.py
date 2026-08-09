import pytest

from cdm.store.indexer import to_document
from cdm.store.mapping_validation import audit_document, validate_document


@pytest.mark.parametrize(
    ("resource", "record", "target"),
    [
        ("bill", {"id": "bill:118:hr:1", "title": "Example"}, "legislation"),
        ("law", {"id": "law:118:pub:1", "title": "Example"}, "legislation"),
        (
            "house_communication",
            {"id": "house-communication:118:1", "number": 1},
            "communication",
        ),
        (
            "bound_congressional_record",
            {"id": "bound:1", "volume_number": 1},
            "congressional_record",
        ),
        (
            "crsreport",
            {"id": "crs:1", "title": "Example", "summary": "Text"},
            "crsreport",
        ),
    ],
)
def test_representative_documents_match_target_mapping(resource, record, target):
    document = to_document(record, resource)
    audit = validate_document(document, resource)

    assert audit["target"] == target
    assert audit["discriminator_errors"] == {}
    assert audit["unmapped_fields"] == []


def test_audit_reports_unmapped_fields_without_silently_dropping_them():
    document = to_document(
        {"id": "bill:118:hr:1", "title": "Example", "future_field": "value"},
        "bill",
    )

    audit = audit_document(document, "bill")

    assert audit["unmapped_fields"] == ["future_field"]
    assert audit["valid"] is True


def test_validate_rejects_wrong_consolidation_discriminator():
    with pytest.raises(ValueError, match="discriminator errors"):
        validate_document(
            {"id": "bill:118:hr:1", "source_type": "law"},
            "bill",
        )
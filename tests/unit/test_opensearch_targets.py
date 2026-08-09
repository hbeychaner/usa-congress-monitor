import pytest

from cdm.store.indexer import to_document
from cdm.store.opensearch import index_name, resource_target, write_alias


@pytest.mark.parametrize(
    ("resource", "index", "metadata"),
    [
        ("bill", "legislation", {"source_type": "bill"}),
        ("law", "legislation", {"source_type": "law"}),
        ("house_communication", "communication", {"chamber": "House"}),
        ("senate_communication", "communication", {"chamber": "Senate"}),
        (
            "bound_congressional_record",
            "congressional_record",
            {"record_subtype": "bound"},
        ),
        (
            "daily_congressional_record",
            "congressional_record",
            {"record_subtype": "daily"},
        ),
        ("congress", "congress_ref", {}),
    ],
)
def test_resource_target_and_alias(resource, index, metadata):
    assert resource_target(resource) == (index, metadata)
    physical_index = index.replace("_", "-")
    assert index_name(resource) == f"congress-{physical_index}"
    assert write_alias(resource) == f"congress-{physical_index}-write"
    assert to_document({"id": "record:1"}, resource)["_resource"] == resource


def test_summaries_cannot_be_indexed_directly():
    with pytest.raises(ValueError, match="cannot be indexed directly"):
        resource_target("summaries")
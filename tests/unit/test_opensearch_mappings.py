from cdm.ingest.runner import Resource
from cdm.store.index_manager import load_definitions
from cdm.store.opensearch import resource_target


def _text_fields(properties):
    for name, definition in properties.items():
        if not isinstance(definition, dict):
            continue
        if definition.get("type") == "text":
            yield name, definition
        nested = definition.get("properties")
        if isinstance(nested, dict):
            yield from _text_fields(nested)


def test_every_indexable_resource_has_a_declared_mapping():
    definitions = load_definitions()

    for resource in Resource:
        if resource.value == "summaries":
            continue
        target, _ = resource_target(resource.value)
        assert target in definitions, (resource.value, target)


def test_consolidated_discriminators_are_mapped():
    definitions = load_definitions()
    properties = definitions["legislation"]["mappings"]["properties"]
    assert "source_type" in properties

    properties = definitions["communication"]["mappings"]["properties"]
    assert "chamber" in properties

    properties = definitions["congressional_record"]["mappings"]["properties"]
    assert "record_subtype" in properties


def test_mapping_file_is_valid_yaml():
    definitions = load_definitions()
    assert isinstance(definitions, dict)
    assert all(isinstance(value, dict) for value in definitions.values())


def test_every_text_field_has_whitespace_analyzed_lemma_multifield():
    definitions = load_definitions()
    text_fields = [
        (index_name, field_name, field)
        for index_name, definition in definitions.items()
        for field_name, field in _text_fields(
            definition.get("mappings", {}).get("properties", {})
        )
    ]

    assert text_fields
    for index_name, field_name, field in text_fields:
        assert field.get("fields", {}).get("lemma") == {
            "type": "text",
            "analyzer": "whitespace",
        }, (
            index_name,
            field_name,
        )

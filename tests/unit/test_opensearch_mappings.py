from cdm.ingest.runner import Resource
from cdm.store.index_manager import load_definitions
from cdm.store.opensearch import resource_target


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


def test_action_source_system_is_mapped_as_an_object():
    properties = load_definitions()["legislation"]["mappings"]["properties"]
    source_system = properties["actions"]["properties"]["source_system"]

    assert source_system["type"] == "object"
    assert source_system["dynamic"] is False
    assert source_system["properties"] == {
        "name": {"type": "keyword"},
        "code": {"type": "integer"},
    }


def test_mapping_file_is_valid_yaml():
    definitions = load_definitions()
    assert isinstance(definitions, dict)
    assert all(isinstance(value, dict) for value in definitions.values())


def test_lemma_multifields_cover_exactly_the_semantic_text_fields():
    """Lemmas are reserved for semantically meaningful free text (semantic
    search / topic modeling); names, committee names, and formulaic action
    strings are keyword-only."""
    from cdm.store.index_manager import lemma_field_paths

    expected = {
        "legislation": {
            ("title",),
            ("full_text",),
            ("summaries", "text"),
            ("notes", "text"),
            ("amendments", "description"),
            ("amendments", "purpose"),
        },
        "amendment": {("description",), ("purpose",)},
        "nomination": {("description",)},
        "treaty": {("topic",)},
        "crsreport": {("title",), ("summary",)},
        "member": set(),
        "committee": set(),
        "communication": set(),
        "sponsorship": set(),
        "vote_position": set(),
    }
    for index_name, paths in expected.items():
        assert set(lemma_field_paths(index_name)) == paths, index_name


def _lemma_multifield_parents(properties):
    for name, definition in properties.items():
        if not isinstance(definition, dict):
            continue
        if definition.get("type") == "text" and "lemma" in definition.get("fields", {}):
            yield name, properties
        nested = definition.get("properties")
        if isinstance(nested, dict):
            yield from _lemma_multifield_parents(nested)


def test_loader_injects_lemma_sibling_for_every_lemma_multifield():
    definitions = load_definitions()

    checked = 0
    for definition in definitions.values():
        properties = definition.get("mappings", {}).get("properties", {})
        for field_name, parent in _lemma_multifield_parents(properties):
            checked += 1
            assert parent.get(f"{field_name}_lemma") == {
                "type": "text",
                "analyzer": "whitespace",
            }, field_name
    assert checked


def test_lemma_field_paths_cover_nested_and_top_level_fields():
    from cdm.store.index_manager import lemma_field_paths

    paths = lemma_field_paths("legislation")

    assert ("title",) in paths
    assert ("full_text",) in paths
    assert ("summaries", "text") in paths
    assert lemma_field_paths("unknown-index") == ()

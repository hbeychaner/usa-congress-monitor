from cdm.store.index_manager import MAPPING_VERSION, IndexManager, load_definitions


class FakeIndices:
    def __init__(self):
        self.created = []
        self.aliases = []
        self.existing = set()

    def exists(self, index):
        return index in self.existing

    def create(self, index, body):
        self.created.append((index, body))
        self.existing.add(index)

    def put_alias(self, index, name):
        self.aliases.append((index, name))

    def update_aliases(self, body):
        self.alias_update = body

    def get(self, index):
        if index == "congress-*":
            return {
                "congress-legislation": {
                    "mappings": {"properties": {"id": {"type": "keyword"}}},
                    "settings": {},
                }
            }
        mapping = load_definitions()["legislation"]["mappings"].copy()
        mapping["_meta"] = {"mapping_version": MAPPING_VERSION}
        return {index: {"mappings": mapping}}

    def get_alias(self, index=None, name=None, ignore=None):
        del ignore
        if name is not None:
            return {
                index: {"aliases": {name: {}}}
                for index in self.existing
                if index == "congress-legislation"
            }
        if index == "congress-legislation-v2":
            return {index: {"aliases": {}}}
        return {"congress-legislation": {"aliases": {"congress-legislation-write": {}}}}


class FakeClient:
    def __init__(self):
        self.indices = FakeIndices()
        self.reindexed = []
        self.indices.alias_update = None

    def count(self, index):
        return {"count": 3}

    def reindex(self, **kwargs):
        self.reindexed.append(kwargs)
        return {"created": 3, "failures": []}

    def search(self, index, body):
        return {
            "hits": {
                "hits": [
                    {"_id": "bill:1", "_source": {"id": "bill:1"}},
                    {"_id": "bill:2", "_source": {"id": "bill:2"}},
                ]
            }
        }


def test_audit_reports_targets_and_unexpected_indices():
    client = FakeClient()

    audit = IndexManager(client).audit()

    legislation = audit["targets"][0]
    assert audit["declared_count"] == len(load_definitions())
    assert legislation["doc_count"] == 3
    assert legislation["aliases"] == ["congress-legislation-write"]
    assert "congress-legislation" not in audit["unexpected_physical_indices"]
    assert audit["staging_indices"] == []


def test_create_adds_write_alias_for_logical_index():
    client = FakeClient()

    IndexManager(client).create("legislation")

    assert client.indices.created[0][0] == "congress-legislation"
    assert client.indices.alias_update == {
        "actions": [
            {
                "add": {
                    "index": "congress-legislation",
                    "alias": "congress-legislation-read",
                }
            },
            {
                "add": {
                    "index": "congress-legislation",
                    "alias": "congress-legislation-write",
                }
            },
        ]
    }


def test_create_versioned_does_not_change_live_aliases():
    client = FakeClient()

    index = IndexManager(client).create_versioned("legislation")

    assert index == "congress-legislation-v2"
    assert client.indices.created[-1][0] == index
    assert client.indices.aliases == []


def test_versioned_mapping_has_explicit_metadata():
    definition = load_definitions()["legislation"]

    mapping = IndexManager._versioned_mapping(definition)["mappings"]

    assert mapping["_meta"] == {"mapping_version": MAPPING_VERSION}
    assert "_meta" not in definition["mappings"]


def test_reindex_to_versioned_preserves_source_target_and_aliases():
    client = FakeClient()

    result = IndexManager(client).reindex_to_versioned("legislation")

    assert result["created"] == 3
    assert client.reindexed == [
        {
            "body": {
                "source": {"index": "congress-legislation"},
                "dest": {"index": "congress-legislation-v2"},
            },
            "wait_for_completion": True,
            "refresh": True,
            "requests_per_second": -1,
        }
    ]
    assert client.indices.aliases == []


def test_validate_versioned_checks_mapping_counts_and_document_ids():
    client = FakeClient()
    IndexManager(client).create_versioned("legislation")

    result = IndexManager(client).validate_versioned("legislation")

    assert result["valid"] is True
    assert result["source_count"] == result["target_count"] == 3
    assert result["mapping_match"] is True
    assert result["sample_id_mismatches"] == []


def test_switch_aliases_to_versioned_is_atomic_and_moves_both_aliases():
    client = FakeClient()
    manager = IndexManager(client)
    manager.create_versioned("legislation")

    result = manager.switch_aliases_to_versioned("legislation")

    assert result["source"] == "congress-legislation"
    assert result["target"] == "congress-legislation-v2"
    assert client.indices.alias_update == {
        "actions": [
            {
                "remove": {
                    "index": "congress-legislation",
                    "alias": "congress-legislation-read",
                }
            },
            {
                "remove": {
                    "index": "congress-legislation",
                    "alias": "congress-legislation-write",
                }
            },
            {
                "add": {
                    "index": "congress-legislation-v2",
                    "alias": "congress-legislation-read",
                }
            },
            {
                "add": {
                    "index": "congress-legislation-v2",
                    "alias": "congress-legislation-write",
                }
            },
        ]
    }

import os

import pytest

from cdm.store.client import get_opensearch_client
from cdm.store.index_manager import IndexManager, load_definitions
from cdm.store.indexer import to_document
from cdm.store.opensearch import (
    bulk_upsert,
    index_name,
    read_alias,
    resource_target,
    write_alias,
)

pytestmark = pytest.mark.integration


def _delete_from_alias_targets(client, alias, document_id):
    for index in client.indices.get_alias(name=alias):
        client.delete(index=index, id=document_id, ignore=[404], refresh=True)


def test_live_index_create_alias_upsert_and_retrieve():
    if os.getenv("OPENSEARCH_INTEGRATION") != "1":
        pytest.skip("Set OPENSEARCH_INTEGRATION=1 to test a live OpenSearch cluster")

    client = get_opensearch_client()
    index = index_name("legislation")
    manager = IndexManager(client)

    try:
        if not client.indices.exists(index=index):
            manager.create("legislation")
        assert client.indices.exists(index=index)
        assert client.indices.exists_alias(name=write_alias("legislation"))

        document = to_document(
            {
                "id": "bill:118:hr:999999",
                "title": "A test bill",
            },
            "bill",
        )
        result = bulk_upsert(client, "bill", [document])
        client.indices.refresh(index=index)
        stored = client.get(index=read_alias("legislation"), id=document["id"])

        assert result["updated"] == 1
        assert stored["_source"]["source_type"] == "bill"
        assert stored["_source"]["title"] == "A test bill"
    finally:
        _delete_from_alias_targets(client, write_alias("legislation"), document["id"])


def test_live_all_declared_targets_accept_round_trip_documents():
    if os.getenv("OPENSEARCH_INTEGRATION") != "1":
        pytest.skip("Set OPENSEARCH_INTEGRATION=1 to test a live OpenSearch cluster")

    client = get_opensearch_client()
    manager = IndexManager(client)
    marker = "acceptance-roundtrip"
    documents = []

    for target in load_definitions():
        if not client.indices.exists(index=index_name(target)):
            manager.create(target)
        resource_target(target)
        document = to_document({"id": f"{marker}:{target}"}, target)
        documents.append((target, document))

    try:
        for target, document in documents:
            alias_targets = client.indices.get_alias(
                name=read_alias(target), ignore=404
            )
            assert list(alias_targets) == [index_name(target)], (target, alias_targets)
            result = bulk_upsert(client, target, [document])
            client.indices.refresh(index=index_name(target))
            stored = client.get(index=read_alias(target), id=document["id"])
            assert result["errors"] is False, (target, result)
            assert stored["_source"]["id"] == document["id"]
    finally:
        for target, document in documents:
            _delete_from_alias_targets(client, write_alias(target), document["id"])

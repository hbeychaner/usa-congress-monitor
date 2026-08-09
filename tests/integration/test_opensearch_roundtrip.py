import os

import pytest

from cdm.store.client import get_opensearch_client
from cdm.store.index_manager import IndexManager
from cdm.store.indexer import to_document
from cdm.store.opensearch import bulk_upsert, index_name, write_alias

pytestmark = pytest.mark.integration


def test_live_index_create_alias_upsert_and_retrieve():
    if os.getenv("OPENSEARCH_INTEGRATION") != "1":
        pytest.skip("Set OPENSEARCH_INTEGRATION=1 to test a live OpenSearch cluster")

    client = get_opensearch_client()
    index = index_name("legislation")
    manager = IndexManager(client)

    try:
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
        stored = client.get(index=index, id=document["id"])

        assert result["updated"] == 1
        assert stored["_source"]["source_type"] == "bill"
        assert stored["_source"]["title"] == "A test bill"
    finally:
        client.indices.delete(index=index, ignore_unavailable=True)

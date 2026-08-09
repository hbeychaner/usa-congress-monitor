import os

import pytest

from cdm.store.client import check_opensearch_connection, get_opensearch_client

pytestmark = pytest.mark.integration


def test_live_opensearch_connection():
    if os.getenv("OPENSEARCH_INTEGRATION") != "1":
        pytest.skip("Set OPENSEARCH_INTEGRATION=1 to test a live OpenSearch cluster")

    client = get_opensearch_client()
    info = check_opensearch_connection(client)

    assert info.get("cluster_name")
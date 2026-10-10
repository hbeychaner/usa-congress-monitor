import pytest

from cdm.config import ElasticConfig
from cdm.store.client import ElasticClientFactory, check_opensearch_connection


def test_factory_requires_url():
    factory = ElasticClientFactory(ElasticConfig(es_local_url="", es_local_api_key="key"))

    with pytest.raises(ValueError, match="URL is not configured"):
        factory.create()


def test_factory_requires_api_key():
    config = ElasticConfig(es_local_url="http://localhost:9200", es_local_api_key="")

    with pytest.raises(ValueError, match="API key is not configured"):
        ElasticClientFactory(config).create()


def test_check_opensearch_connection_delegates_to_client():
    class FakeClient:
        def info(self):
            return {"cluster_name": "test"}

    assert check_opensearch_connection(FakeClient()) == {"cluster_name": "test"}
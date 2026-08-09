import pytest

from cdm.store.client import check_opensearch_connection, get_opensearch_client


def test_get_opensearch_client_requires_url(monkeypatch):
    monkeypatch.setattr("settings.ES_LOCAL_URL", "")
    monkeypatch.setattr("settings.ES_LOCAL_API_KEY", "key")

    with pytest.raises(ValueError, match="URL is not configured"):
        get_opensearch_client()


def test_get_opensearch_client_requires_api_key(monkeypatch):
    monkeypatch.setattr("settings.ES_LOCAL_URL", "http://localhost:9200")
    monkeypatch.setattr("settings.ES_LOCAL_API_KEY", "")

    with pytest.raises(ValueError, match="API key is not configured"):
        get_opensearch_client()


def test_check_opensearch_connection_delegates_to_client():
    class FakeClient:
        def info(self):
            return {"cluster_name": "test"}

    assert check_opensearch_connection(FakeClient()) == {"cluster_name": "test"}
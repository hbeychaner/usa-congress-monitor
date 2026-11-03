import os
from collections.abc import Iterator
from uuid import uuid4

import httpx
import pytest
from elasticsearch import Elasticsearch

from cdm.backend.app import app
from cdm.backend.dependencies import get_container
from cdm.config import ApiConfig, AppConfig
from cdm.container import Container
from cdm.store.opensearch import read_alias


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[Elasticsearch]:
    url = os.environ.get("HTTP_ERRORS_TEST_URL")
    if not url:
        pytest.skip(
            "Set HTTP_ERRORS_TEST_URL to an empty isolated Elasticsearch server"
        )
    client = Elasticsearch(url, request_timeout=5)
    index = f"http-errors-test-{uuid4().hex}"
    alias = read_alias("bill")
    if client.indices.exists(index=alias):
        client.close()
        raise RuntimeError("HTTP error tests require an empty isolated cluster")
    try:
        client.indices.create(index=index, aliases={alias: {}})
        client.index(
            index=alias,
            id="bill:119:hr:1",
            document={
                "id": "bill:119:hr:1",
                "source_type": "bill",
                "title": "Preserved congressional source record",
            },
            refresh="wait_for",
        )
        container = Container(AppConfig(api=ApiConfig(readiness_timeout_secs=1)))
        container.__dict__["elastic_client"] = client
        monkeypatch.setitem(app.dependency_overrides, get_container, lambda: container)
        yield client
    finally:
        client.indices.delete(index=index, ignore_unavailable=True)
        client.close()


@pytest.mark.asyncio
async def test_real_missing_document_missing_index_readiness_and_source_preservation(
    client: Elasticsearch,
) -> None:
    alias = read_alias("bill")
    source = client.get(index=alias, id="bill:119:hr:1").body
    index = source["_index"]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://fixture"
    ) as api:
        existing = await api.get("/api/v1/bills/bill:119:hr:1")
        missing = await api.get("/api/v1/bills/bill:119:hr:2")
        ready = await api.get("/ready")
        assert existing.status_code == 200
        assert missing.status_code == 404
        assert missing.json() == {"detail": "Bill not found: bill:119:hr:2"}
        assert ready.status_code == 200
        client.indices.delete_alias(index=index, name=alias)
        unavailable = await api.get("/api/v1/bills/bill:119:hr:1")
        alive = await api.get("/health")
    assert unavailable.status_code == 503
    assert unavailable.json() == {
        "detail": "Search service unavailable; please try again later.",
        "analysis_state": "unavailable",
    }
    assert alive.status_code == 200 and alive.json() == {"status": "ok"}
    assert client.get(index=index, id="bill:119:hr:1").body == source

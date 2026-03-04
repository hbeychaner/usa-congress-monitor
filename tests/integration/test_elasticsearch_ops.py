"""Integration tests for Elasticsearch indexing and search helpers."""

from __future__ import annotations

from typing import Any, AsyncGenerator
from uuid import uuid4

import pytest
from elasticsearch import ApiError, AsyncElasticsearch, NotFoundError

from knowledgebase.client import build_client
from knowledgebase.indexing import index_records
from knowledgebase.indices import SEMANTIC_FIELD, SEMANTIC_INFERENCE_ID
from knowledgebase.search import (
    search_by_id,
    search_hybrid,
    search_semantic_only,
    search_text_only,
)
from settings import (
    ELASTIC_API_KEY,
    ELASTIC_API_URL,
    ES_LOCAL_API_KEY,
    ES_LOCAL_URL,
)


@pytest.fixture(scope="module")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="module")
async def elastic_client() -> AsyncGenerator[AsyncElasticsearch, None]:
    url = ELASTIC_API_URL or ES_LOCAL_URL
    api_key = ELASTIC_API_KEY or ES_LOCAL_API_KEY
    if not url or not api_key:
        pytest.skip("Elasticsearch credentials not configured")
    client = build_client(url, api_key)
    try:
        yield client
    finally:
        await client.close()


async def _has_inference_endpoint(client: AsyncElasticsearch, endpoint_id: str) -> bool:
    path = f"/_inference/sparse_embedding/{endpoint_id}"
    try:
        await client.transport.perform_request(
            "GET", path, headers={"accept": "application/json"}
        )
        return True
    except NotFoundError:
        return False
    except ApiError:
        return False


@pytest.fixture()
async def es_test_index(
    elastic_client: AsyncElasticsearch,
) -> AsyncGenerator[dict[str, Any], None]:
    semantic_enabled = await _has_inference_endpoint(
        elastic_client, SEMANTIC_INFERENCE_ID
    )
    index_name = f"kb-test-{uuid4().hex[:8]}"

    if semantic_enabled:
        title_mapping = {"type": "text", "fields": {"semantic": SEMANTIC_FIELD}}
        text_mapping = {"type": "text", "fields": {"semantic": SEMANTIC_FIELD}}
    else:
        title_mapping = {"type": "text"}
        text_mapping = {"type": "text"}

    mapping = {
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "title": title_mapping,
                "text": text_mapping,
            }
        }
    }

    await elastic_client.indices.create(index=index_name, mappings=mapping["mappings"])

    try:
        yield {"name": index_name, "semantic": semantic_enabled}
    finally:
        await elastic_client.indices.delete(index=index_name, ignore_unavailable=True)


async def _index_sample_docs(client: AsyncElasticsearch, index_name: str) -> None:
    docs = [
        {
            "id": "doc-1",
            "title": "Keystone XL Pipeline Approval Act",
            "text": "Pipeline approval for energy infrastructure.",
        },
        {
            "id": "doc-2",
            "title": "Clean Energy Tax Credits Act",
            "text": "Tax credits supporting clean energy deployment.",
        },
    ]

    await index_records(
        client, index_name, docs, lambda record: record["id"], chunk_size=50
    )
    await client.indices.refresh(index=index_name)


@pytest.mark.anyio
async def test_indexing_and_keyword_search(
    elastic_client: AsyncElasticsearch, es_test_index
) -> None:
    index_name = es_test_index["name"]
    await _index_sample_docs(elastic_client, index_name)

    response = await search_by_id(elastic_client, index_name, "doc-1")
    hits = response.get("hits", {}).get("hits", [])
    assert hits, "Expected at least one hit for id query"
    assert hits[0].get("_source", {}).get("id") == "doc-1"


@pytest.mark.anyio
async def test_text_search(elastic_client: AsyncElasticsearch, es_test_index) -> None:
    index_name = es_test_index["name"]
    await _index_sample_docs(elastic_client, index_name)

    response = await search_text_only(
        elastic_client, index_name, "tax credits", ["title", "text"]
    )
    hits = response.get("hits", {}).get("hits", [])
    assert hits, "Expected hits for text query"


@pytest.mark.anyio
async def test_semantic_and_hybrid_search(
    elastic_client: AsyncElasticsearch, es_test_index
) -> None:
    if not es_test_index["semantic"]:
        pytest.skip("Semantic inference endpoint not available")

    index_name = es_test_index["name"]
    await _index_sample_docs(elastic_client, index_name)

    semantic_response = await search_semantic_only(
        elastic_client,
        index_name,
        "pipeline approval",
        "title.semantic",
    )
    semantic_hits = semantic_response.get("hits", {}).get("hits", [])
    assert semantic_hits, "Expected hits for semantic query"

    hybrid_response = await search_hybrid(
        elastic_client,
        index_name,
        "clean energy",
        text_fields=["title", "text"],
        semantic_fields=["title.semantic", "text.semantic"],
    )
    hybrid_hits = hybrid_response.get("hits", {}).get("hits", [])
    assert hybrid_hits, "Expected hits for hybrid query"

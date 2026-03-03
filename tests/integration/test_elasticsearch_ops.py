"""Integration tests for Elasticsearch indexing and search helpers."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from elasticsearch import ApiError, Elasticsearch, NotFoundError

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
def elastic_client() -> Elasticsearch:
    url = ELASTIC_API_URL or ES_LOCAL_URL
    api_key = ELASTIC_API_KEY or ES_LOCAL_API_KEY
    if not url or not api_key:
        pytest.skip("Elasticsearch credentials not configured")
    return build_client(url, api_key)


def _has_inference_endpoint(client: Elasticsearch, endpoint_id: str) -> bool:
    path = f"/_inference/sparse_embedding/{endpoint_id}"
    try:
        client.transport.perform_request(
            "GET", path, headers={"accept": "application/json"}
        )
        return True
    except NotFoundError:
        return False
    except ApiError:
        return False


@pytest.fixture()
def es_test_index(elastic_client: Elasticsearch) -> dict[str, Any]:
    semantic_enabled = _has_inference_endpoint(elastic_client, SEMANTIC_INFERENCE_ID)
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

    elastic_client.indices.create(index=index_name, mappings=mapping["mappings"])

    try:
        yield {"name": index_name, "semantic": semantic_enabled}
    finally:
        elastic_client.indices.delete(index=index_name, ignore_unavailable=True)


def _index_sample_docs(client: Elasticsearch, index_name: str) -> None:
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

    index_records(client, index_name, docs, lambda record: record["id"], chunk_size=50)
    client.indices.refresh(index=index_name)


def test_indexing_and_keyword_search(elastic_client: Elasticsearch, es_test_index) -> None:
    index_name = es_test_index["name"]
    _index_sample_docs(elastic_client, index_name)

    response = search_by_id(elastic_client, index_name, "doc-1")
    hits = response.get("hits", {}).get("hits", [])
    assert hits, "Expected at least one hit for id query"
    assert hits[0].get("_source", {}).get("id") == "doc-1"


def test_text_search(elastic_client: Elasticsearch, es_test_index) -> None:
    index_name = es_test_index["name"]
    _index_sample_docs(elastic_client, index_name)

    response = search_text_only(elastic_client, index_name, "tax credits", ["title", "text"])
    hits = response.get("hits", {}).get("hits", [])
    assert hits, "Expected hits for text query"


def test_semantic_and_hybrid_search(elastic_client: Elasticsearch, es_test_index) -> None:
    if not es_test_index["semantic"]:
        pytest.skip("Semantic inference endpoint not available")

    index_name = es_test_index["name"]
    _index_sample_docs(elastic_client, index_name)

    semantic_response = search_semantic_only(
        elastic_client,
        index_name,
        "pipeline approval",
        "title.semantic",
    )
    semantic_hits = semantic_response.get("hits", {}).get("hits", [])
    assert semantic_hits, "Expected hits for semantic query"

    hybrid_response = search_hybrid(
        elastic_client,
        index_name,
        "clean energy",
        text_fields=["title", "text"],
        semantic_fields=["title.semantic", "text.semantic"],
    )
    hybrid_hits = hybrid_response.get("hits", {}).get("hits", [])
    assert hybrid_hits, "Expected hits for hybrid query"

"""Run search helper smoke tests using real documents from Elasticsearch."""

from __future__ import annotations

from typing import Any

import pytest
from elasticsearch import AsyncElasticsearch

from knowledgebase.client import build_client
from settings import ELASTIC_API_KEY, ELASTIC_API_URL, ES_LOCAL_API_KEY, ES_LOCAL_URL
from knowledgebase.search import (
    search_by_id,
    search_hybrid,
    search_semantic_only,
    search_text_only,
)


@pytest.fixture(scope="module")
def anyio_backend() -> str:
    return "asyncio"


def get_client() -> AsyncElasticsearch:
    url = ELASTIC_API_URL or ES_LOCAL_URL
    api_key = ELASTIC_API_KEY or ES_LOCAL_API_KEY
    if not url or not api_key:
        raise RuntimeError("ELASTIC_API_URL and ELASTIC_API_KEY are required")
    return build_client(url, api_key)


async def get_sample_doc(
    client: AsyncElasticsearch, index_name: str
) -> dict[str, Any] | None:
    resp = await client.search(index=index_name, size=1)
    hits = resp.get("hits", {}).get("hits", [])
    if not hits:
        return None
    return hits[0].get("_source", {})


def print_hits(label: str, response: dict[str, Any], max_hits: int = 3) -> None:
    hits = response.get("hits", {}).get("hits", [])
    print(f"{label}: {len(hits)} hits")
    for hit in hits[:max_hits]:
        source = hit.get("_source", {})
        print(
            "  -", source.get("title") or source.get("fullName") or source.get("name")
        )


@pytest.mark.anyio
async def test_member_search() -> None:
    client = get_client()
    try:
        index_name = "congress-members"
        sample = await get_sample_doc(client, index_name)
        if not sample:
            print("No documents found in congress-members; skipping member tests")
            return

        sample_id = sample.get("id") or sample.get("bioguideId")
        if sample_id:
            resp = await search_by_id(client, index_name, str(sample_id))
            print_hits("Member keyword id search", resp)

        text_value = sample.get("fullName") or sample.get("name") or sample.get("party")
        if text_value:
            resp = await search_text_only(
                client,
                index_name,
                str(text_value),
                ["fullName", "name", "party", "state"],
            )
            print_hits("Member text-only search", resp)
    finally:
        await client.close()


@pytest.mark.anyio
async def test_bill_search() -> None:
    client = get_client()
    try:
        index_name = "congress-bills"
        sample = await get_sample_doc(client, index_name)
        if not sample:
            print("No documents found in congress-bills; skipping bill tests")
            return

        title = sample.get("title") or "energy"
        resp = await search_text_only(
            client, index_name, str(title), ["title", "latestAction.text"]
        )
        print_hits("Bill text-only search", resp)

        resp = await search_semantic_only(
            client, index_name, str(title), "title.semantic"
        )
        print_hits("Bill semantic-only search", resp)

        resp = await search_hybrid(
            client,
            index_name,
            str(title),
            text_fields=["title", "latestAction.text"],
            semantic_fields=["title.semantic", "latestAction.text.semantic"],
        )
        print_hits("Bill hybrid search", resp)
    finally:
        await client.close()


def main() -> None:
    raise RuntimeError("Use pytest or run the async helpers explicitly.")


if __name__ == "__main__":
    main()

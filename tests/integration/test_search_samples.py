"""Run search helper smoke tests using real documents from Elasticsearch."""

from __future__ import annotations

from typing import Any

from elasticsearch import Elasticsearch

from knowledgebase.client import build_client
from settings import ELASTIC_API_KEY, ELASTIC_API_URL, ES_LOCAL_API_KEY, ES_LOCAL_URL
from knowledgebase.search import (
    search_by_id,
    search_hybrid,
    search_semantic_only,
    search_text_only,
)


def get_client() -> Elasticsearch:
    url = ELASTIC_API_URL or ES_LOCAL_URL
    api_key = ELASTIC_API_KEY or ES_LOCAL_API_KEY
    if not url or not api_key:
        raise RuntimeError("ELASTIC_API_URL and ELASTIC_API_KEY are required")
    return build_client(url, api_key)


def get_sample_doc(client: Elasticsearch, index_name: str) -> dict[str, Any] | None:
    resp = client.search(index=index_name, size=1)
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


def test_member_search() -> None:
    client = get_client()
    index_name = "congress-members"
    sample = get_sample_doc(client, index_name)
    if not sample:
        print("No documents found in congress-members; skipping member tests")
        return

    sample_id = sample.get("id") or sample.get("bioguideId")
    if sample_id:
        resp = search_by_id(client, index_name, str(sample_id))
        print_hits("Member keyword id search", resp)

    text_value = sample.get("fullName") or sample.get("name") or sample.get("party")
    if text_value:
        resp = search_text_only(
            client, index_name, str(text_value), ["fullName", "name", "party", "state"]
        )  # noqa: E501
        print_hits("Member text-only search", resp)


def test_bill_search() -> None:
    client = get_client()
    index_name = "congress-bills"
    sample = get_sample_doc(client, index_name)
    if not sample:
        print("No documents found in congress-bills; skipping bill tests")
        return

    title = sample.get("title") or "energy"
    resp = search_text_only(
        client, index_name, str(title), ["title", "latestAction.text"]
    )  # noqa: E501
    print_hits("Bill text-only search", resp)

    resp = search_semantic_only(client, index_name, str(title), "title.semantic")
    print_hits("Bill semantic-only search", resp)

    resp = search_hybrid(
        client,
        index_name,
        str(title),
        text_fields=["title", "latestAction.text"],
        semantic_fields=["title.semantic", "latestAction.text.semantic"],
    )
    print_hits("Bill hybrid search", resp)


def main() -> None:
    client = get_client()
    test_member_search(client)
    test_bill_search(client)


if __name__ == "__main__":
    main()

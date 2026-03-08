"""Search helpers for querying knowledgebase indices."""

from __future__ import annotations

from typing import Any

from elasticsearch import AsyncElasticsearch


async def search_index(
    client: AsyncElasticsearch,
    index_name: str,
    query: dict[str, Any],
    size: int = 10,
) -> dict[str, Any]:
    """Run a search query against an index."""
    result = await client.search(index=index_name, query=query, size=size)
    return result.to_dict()


def multi_match_query(text: str, fields: list[str]) -> dict[str, Any]:
    """Build a multi_match query payload."""
    return {
        "multi_match": {
            "query": text,
            "fields": fields,
        }
    }


def keyword_id_query(id_value: str, field: str = "id") -> dict[str, Any]:
    """Build a keyword-only id query."""
    return {"term": {field: id_value}}


def text_query(text: str, fields: list[str]) -> dict[str, Any]:
    """Build a text-only query across fields."""
    return multi_match_query(text, fields)


def semantic_query(text: str, field: str) -> dict[str, Any]:
    """Build a semantic query for a single semantic_text field."""
    return {"semantic": {"field": field, "query": text}}


def hybrid_query(
    text: str,
    text_fields: list[str],
    semantic_fields: list[str],
    text_boost: float = 1.0,
    semantic_boost: float = 1.0,
) -> dict[str, Any]:
    """Build a hybrid query combining text and semantic clauses."""
    should_clauses: list[dict[str, Any]] = [
        {"multi_match": {"query": text, "fields": text_fields, "boost": text_boost}}
    ]
    for field in semantic_fields:
        should_clauses.append(
            {"semantic": {"field": field, "query": text, "boost": semantic_boost}}
        )
    return {"bool": {"should": should_clauses, "minimum_should_match": 1}}


async def search_by_id(
    client: AsyncElasticsearch,
    index_name: str,
    id_value: str,
    field: str = "id",
) -> dict[str, Any]:
    """Keyword-only search by id field."""
    return await search_index(
        client, index_name, keyword_id_query(id_value, field), size=1
    )


async def search_text_only(
    client: AsyncElasticsearch,
    index_name: str,
    text: str,
    fields: list[str],
    size: int = 10,
) -> dict[str, Any]:
    """Text-only search across fields."""
    return await search_index(client, index_name, text_query(text, fields), size=size)


async def search_semantic_only(
    client: AsyncElasticsearch,
    index_name: str,
    text: str,
    field: str,
    size: int = 10,
) -> dict[str, Any]:
    """Semantic-only search for a single semantic_text field."""
    return await search_index(client, index_name, semantic_query(text, field), size=size)


async def search_hybrid(
    client: AsyncElasticsearch,
    index_name: str,
    text: str,
    text_fields: list[str],
    semantic_fields: list[str],
    size: int = 10,
    text_boost: float = 1.0,
    semantic_boost: float = 1.0,
) -> dict[str, Any]:
    """Hybrid search combining text and semantic queries."""
    query = hybrid_query(
        text,
        text_fields=text_fields,
        semantic_fields=semantic_fields,
        text_boost=text_boost,
        semantic_boost=semantic_boost,
    )
    return await search_index(client, index_name, query, size=size)

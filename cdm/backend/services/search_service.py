from __future__ import annotations

import logging
from typing import Any

from cdm.backend.services.state_service import list_states
from cdm.contracts.api import SearchResponse, SearchResultItem
from cdm.store.client import get_opensearch_client
from cdm.store.opensearch import read_alias

SUPPORTED_TYPES = {"member", "state", "bill"}
logger = logging.getLogger(__name__)


def _normalized_types(types: str) -> list[str]:
    selected = [t.strip().lower() for t in types.split(",") if t.strip()]
    filtered = [t for t in selected if t in SUPPORTED_TYPES]
    if filtered:
        return filtered
    return ["member", "state", "bill"]


def _state_results(query: str, limit: int) -> list[SearchResultItem]:
    needle = query.strip().lower()
    if not needle:
        return []
    results: list[SearchResultItem] = []
    for state in list_states():
        if needle in state.name.lower() or needle in state.code.lower():
            results.append(
                SearchResultItem(
                    id=state.code,
                    result_type="state",
                    title=state.name,
                    subtitle=state.code,
                )
            )
            if len(results) >= limit:
                break
    return results


def _member_query(query: str, size: int) -> dict[str, Any]:
    return {
        "size": size,
        "query": {
            "bool": {
                "should": [
                    {"term": {"bioguide_id": {"value": query.upper(), "boost": 6}}},
                    {"term": {"state_code": {"value": query.upper(), "boost": 4}}},
                    {"match_phrase_prefix": {"name": {"query": query, "boost": 4}}},
                    {"match_phrase_prefix": {"full_name": {"query": query, "boost": 4}}},
                    {"match_phrase_prefix": {"direct_order_name": {"query": query, "boost": 4}}},
                    {
                        "multi_match": {
                            "query": query,
                            "fields": [
                                "name^3",
                                "full_name^3",
                                "direct_order_name^3",
                                "inverted_order_name^2",
                                "first_name^2",
                                "last_name^2",
                                "party_name^1.5",
                                "party^1.5",
                                "state^1.5",
                            ],
                            "fuzziness": "AUTO",
                        }
                    },
                    {"term": {"state": {"value": query.upper(), "boost": 2}}},
                ],
                "minimum_should_match": 1,
            }
        },
        "sort": ["_score"],
    }


def _bill_query(query: str, size: int) -> dict[str, Any]:
    return {
        "size": size,
        "query": {
            "bool": {
                "should": [
                    {"term": {"id": {"value": query.lower(), "boost": 6}}},
                    {"term": {"number": {"value": query, "boost": 4}}},
                    {"match_phrase_prefix": {"title": {"query": query, "boost": 3}}},
                    {
                        "multi_match": {
                            "query": query,
                            "fields": [
                                "title^3",
                                "latest_action_text^2",
                                "latest_action.text^2",
                                "actions.text",
                            ],
                            "fuzziness": "AUTO",
                        }
                    },
                ],
                "minimum_should_match": 1,
            }
        },
        "sort": ["_score"],
    }


def _normalize_member_id(raw_id: str) -> str:
    if raw_id.startswith("person:"):
        return raw_id.split(":", 1)[1]
    return raw_id


def _search_members(client: Any, query: str, limit: int) -> list[SearchResultItem]:
    response = client.search(
        index=read_alias("member"), body=_member_query(query, limit)
    )
    hits = response.get("hits", {}).get("hits", [])
    items: list[SearchResultItem] = []
    for hit in hits:
        source = hit.get("_source", {})
        raw_id = str(source.get("bioguide_id") or source.get("id") or hit.get("_id", ""))
        bioguide_id = _normalize_member_id(raw_id)
        if not bioguide_id:
            continue
        subtitle_parts = [
            source.get("party_name") or source.get("party"),
            source.get("state_code") or source.get("state"),
        ]
        subtitle = " - ".join(part for part in subtitle_parts if part)
        items.append(
            SearchResultItem(
                id=str(bioguide_id),
                result_type="member",
                title=str(
                    source.get("name")
                    or source.get("full_name")
                    or source.get("direct_order_name")
                    or bioguide_id
                ),
                subtitle=subtitle or None,
            )
        )
    return items


def _search_bills(client: Any, query: str, limit: int) -> list[SearchResultItem]:
    response = client.search(
        index=read_alias("bill"),
        body=_bill_query(query, limit),
    )
    hits = response.get("hits", {}).get("hits", [])
    items: list[SearchResultItem] = []
    for hit in hits:
        source = hit.get("_source", {})
        bill_id = str(source.get("id") or hit.get("_id") or "")
        if not bill_id:
            continue
        congress = source.get("congress")
        bill_type = source.get("bill_type")
        number = source.get("number")
        subtitle = " ".join(str(part) for part in (bill_type, number) if part)
        if congress:
            subtitle = f"Congress {congress}" + (f" - {subtitle}" if subtitle else "")
        items.append(
            SearchResultItem(
                id=bill_id,
                result_type="bill",
                title=str(source.get("title") or bill_id),
                subtitle=subtitle or None,
            )
        )
    return items


def search_entities(q: str, types: str, limit: int) -> SearchResponse:
    normalized_types = _normalized_types(types)
    query = q.strip()
    if not query:
        return SearchResponse(query=q, types=normalized_types, limit=limit, results=[])

    per_type_limit = max(1, min(limit, 50))
    results: list[SearchResultItem] = []

    if "state" in normalized_types:
        results.extend(_state_results(query, per_type_limit))

    try:
        client = get_opensearch_client()
        if "member" in normalized_types:
            results.extend(_search_members(client, query, per_type_limit))
        if "bill" in normalized_types:
            results.extend(_search_bills(client, query, per_type_limit))
    except Exception as exc:
        logger.warning(
            "OpenSearch search unavailable; returning partial results", exc_info=exc
        )

    return SearchResponse(
        query=q,
        types=normalized_types,
        limit=limit,
        results=results[:limit],
    )

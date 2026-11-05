"""Cross-entity search over members, states and bills."""

from __future__ import annotations

from elasticsearch import Elasticsearch

from cdm.backend.services.state_service import StateService
from cdm.config.query_reads import QueryReadConfig, SearchKind
from cdm.contracts.api import SearchResponse, SearchResultItem
from cdm.store.bill_scope import BillReadScope
from cdm.store.client import SearchCompletion
from cdm.store.opensearch import read_alias
from cdm.utils.json_types import JsonObject
from cdm.utils.lemmatize import try_lemmatize_query


class SearchService:
    def __init__(
        self,
        client: Elasticsearch,
        states: StateService,
        reads: QueryReadConfig | None = None,
    ) -> None:
        self._client = client
        self._states = states
        self._reads = reads or QueryReadConfig()

    def search(self, q: str, types: str, limit: int) -> SearchResponse:
        self._reads.offset(1, limit)
        self._reads.text(q, "q")
        normalized_types = [
            kind.value for kind in self._reads.selected(types, SearchKind)
        ]
        query = q.strip()
        if not query:
            return SearchResponse(
                query=q, types=normalized_types, limit=limit, results=[]
            )

        results: list[SearchResultItem] = []

        if "state" in normalized_types:
            results.extend(self._state_results(query, limit))

        if "member" in normalized_types:
            results.extend(self.search_members(query, limit))
        if "bill" in normalized_types:
            results.extend(self._search_bills(query, limit))

        return SearchResponse(
            query=q,
            types=normalized_types,
            limit=limit,
            results=results,
        )

    def search_members(self, query: str, limit: int) -> list[SearchResultItem]:
        self._reads.offset(1, limit)
        self._reads.text(query, "q")
        body = self._member_query(query, limit)
        body["_source"] = list(self._reads.member_search_fields)
        response = self._client.search(
            index=read_alias("member"),
            body=body,
            allow_partial_search_results=False,
        )
        SearchCompletion.model_validate(response.body).require_complete()
        hits = response.get("hits", {}).get("hits", [])
        items: list[SearchResultItem] = []
        for hit in hits:
            source = hit.get("_source", {})
            raw_id = str(
                source.get("bioguide_id") or source.get("id") or hit.get("_id", "")
            )
            bioguide_id = self._normalize_member_id(raw_id)
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

    def _search_bills(self, query: str, limit: int) -> list[SearchResultItem]:
        body = self._bill_query(query, limit)
        body["_source"] = list(self._reads.bill_search_fields)
        response = self._client.search(
            index=read_alias("bill"),
            body=body,
            allow_partial_search_results=False,
        )
        SearchCompletion.model_validate(response.body).require_complete()
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
                subtitle = f"Congress {congress}" + (
                    f" - {subtitle}" if subtitle else ""
                )
            items.append(
                SearchResultItem(
                    id=bill_id,
                    result_type="bill",
                    title=str(source.get("title") or bill_id),
                    subtitle=subtitle or None,
                )
            )
        return items

    def _state_results(self, query: str, limit: int) -> list[SearchResultItem]:
        needle = query.strip().lower()
        if not needle:
            return []
        results: list[SearchResultItem] = []
        for state in self._states.list_states():
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

    @staticmethod
    def _normalize_member_id(raw_id: str) -> str:
        if raw_id.startswith("person:"):
            return raw_id.split(":", 1)[1]
        return raw_id

    @staticmethod
    def _member_query(query: str, size: int) -> JsonObject:
        should: list[JsonObject] = [
            {"term": {"bioguide_id": {"value": query.upper(), "boost": 6}}},
            {"term": {"state_code": {"value": query.upper(), "boost": 4}}},
            {"match_phrase_prefix": {"name": {"query": query, "boost": 4}}},
            {"match_phrase_prefix": {"full_name": {"query": query, "boost": 4}}},
            {
                "match_phrase_prefix": {
                    "direct_order_name": {"query": query, "boost": 4}
                }
            },
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
        ]
        return {
            "size": size,
            "query": {"bool": {"should": should, "minimum_should_match": 1}},
            "sort": ["_score", {"id": "asc"}],
        }

    @staticmethod
    def _bill_query(query: str, size: int) -> JsonObject:
        identity = BillReadScope.identity_query(query)
        if identity is not None:
            return {
                "size": size,
                "query": {"bool": {"filter": [BillReadScope.query(), identity]}},
                "sort": ["_score", {"id": "asc"}],
            }
        should: list[JsonObject] = [
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
        ]
        lemma_query = try_lemmatize_query(query)
        if lemma_query:
            should.append(
                {
                    "multi_match": {
                        "query": lemma_query,
                        "fields": ["title_lemma^2", "full_text_lemma"],
                    }
                }
            )
        return {
            "size": size,
            "query": {
                "bool": {
                    "filter": [BillReadScope.query()],
                    "should": should,
                    "minimum_should_match": 1,
                }
            },
            "sort": ["_score", {"id": "asc"}],
        }

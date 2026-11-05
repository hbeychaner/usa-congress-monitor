"""Elasticsearch-backed bill listing and detail services."""

from __future__ import annotations

from typing import Any

from elasticsearch import Elasticsearch, NotFoundError
from pydantic import TypeAdapter

from cdm.backend.errors import EntityNotFoundError
from cdm.backend.services.bill_vote_index import BillVoteIndex
from cdm.config.query_reads import QueryReadConfig
from cdm.contracts.api import BillDetail, BillDetailResponse, BillsResponse, BillSummary
from cdm.contracts.hydration import HydrationAssessment
from cdm.store.bill_scope import BillReadScope
from cdm.store.client import SearchCompletion
from cdm.store.opensearch import read_alias
from cdm.utils.json_types import JsonObject
from cdm.utils.lemmatize import try_lemmatize_query


class BillService:
    """Bill listing and detail lookups."""

    def __init__(
        self,
        client: Elasticsearch,
        vote_index: BillVoteIndex,
        reads: QueryReadConfig | None = None,
    ) -> None:
        self._client = client
        self._vote_index = vote_index
        self._reads = reads or QueryReadConfig()

    def list_recent(
        self,
        limit: int = 50,
        page: int = 1,
        query: str | None = None,
        congress: int | None = None,
        bill_type: str | None = None,
        chamber: str | None = None,
        subject: str | None = None,
        has_votes: bool = False,
    ) -> BillsResponse:
        """Return the most recently updated bills from the legislation read alias."""
        offset = self._reads.offset(page, limit)
        if query:
            self._reads.text(query, "query")
        filters: list[dict[str, Any]] = [BillReadScope.query()]
        if congress is not None:
            filters.append({"term": {"congress": congress}})
        if bill_type:
            filters.append({"wildcard": {"id": f"bill:*:{bill_type.lower()}:*"}})
        if chamber:
            filters.append({"term": {"origin_chamber": chamber}})
        if subject:
            filters.append(self._subject_filter(subject))
        if has_votes:
            filters.append({"terms": {"id": self._vote_index.bill_ids(congress)}})
        search_query: dict[str, Any] = {"bool": {"filter": filters}}
        if query and query.strip():
            search_query["bool"]["must"] = [self._text_query(query.strip())]
        response = self._client.search(
            index=read_alias("bill"),
            allow_partial_search_results=False,
            body={
                "from": offset,
                "size": limit,
                "_source": list(self._reads.bill_fields),
                "track_total_hits": True,
                "query": search_query,
                "sort": [
                    {"update_date": {"order": "desc", "missing": "_last"}},
                    {"id": "asc"},
                ],
            },
        )
        SearchCompletion.model_validate(response.body).require_complete()
        hits = response.get("hits", {})
        total = hits.get("total", 0)
        if isinstance(total, dict):
            total = total.get("value", 0)
        bills = [
            summary
            for hit in hits.get("hits", [])
            if (summary := self._summary(hit)) is not None
        ]
        vote_counts = self._vote_index.counts([bill.bill_id for bill in bills])
        for bill in bills:
            bill.vote_count = vote_counts.get(bill.bill_id, 0)
        return BillsResponse(
            bills=bills,
            total=int(total),
            page=page,
            limit=limit,
            max_result_window=self._reads.max_result_window,
        )

    def get(self, bill_id: str) -> BillDetailResponse:
        """Return one bill document from the read alias."""
        normalized_id = bill_id.strip()
        try:
            response = self._client.get(index=read_alias("bill"), id=normalized_id)
        except NotFoundError as exc:
            if isinstance(exc.body, dict) and exc.body.get("found") is False:
                raise EntityNotFoundError(f"Bill not found: {normalized_id}") from exc
            raise
        source = TypeAdapter(JsonObject).validate_python(response.get("_source", {}))
        if not BillReadScope.contains(source, normalized_id):
            raise EntityNotFoundError(f"Bill not found: {normalized_id}")

        policy_area = source.get("policy_area")
        if isinstance(policy_area, dict):
            policy_area = policy_area.get("name")

        actions = self._dict_list(source, "actions")
        actions.sort(key=lambda item: str(item.get("action_date") or ""), reverse=True)
        return BillDetailResponse(
            bill=BillDetail(
                bill_id=str(source.get("id") or normalized_id),
                title=str(source.get("title") or normalized_id),
                congress=source.get("congress"),
                bill_type=source.get("type"),
                number=str(source["number"])
                if source.get("number") is not None
                else None,
                origin_chamber=source.get("origin_chamber"),
                origin_chamber_code=source.get("origin_chamber_code"),
                introduced_date=source.get("introduced_date"),
                update_date=source.get("update_date"),
                update_date_including_text=source.get("update_date_including_text"),
                latest_action=source.get("latest_action"),
                policy_area=policy_area,
                sponsors=self._dict_list(source, "sponsors"),
                cosponsors=self._dict_list(source, "cosponsors"),
                actions=actions,
                summaries=self._dict_list(source, "summaries"),
                titles=self._dict_list(source, "titles"),
                text_versions=self._dict_list(source, "text_versions"),
                committees=self._dict_list(source, "committees"),
                related_bills=self._dict_list(source, "related_bills"),
                subjects=source.get("subjects")
                if isinstance(source.get("subjects"), dict)
                else None,
                laws=self._dict_list(source, "laws"),
                constitutional_authority_statement_text=source.get(
                    "constitutional_authority_statement_text"
                ),
                full_text=source.get("full_text"),
                full_text_version_code=source.get("full_text_version_code"),
                relationship_counts=self._relationship_counts(source),
                hydration=HydrationAssessment.from_record(source),
            )
        )

    @staticmethod
    def _subject_filter(subject: str) -> dict[str, Any]:
        return {
            "bool": {
                "should": [
                    {
                        "nested": {
                            "path": "subjects.legislative_subjects",
                            "query": {
                                "term": {"subjects.legislative_subjects.name": subject}
                            },
                        }
                    },
                    {"term": {"policy_area.name": subject}},
                ],
                "minimum_should_match": 1,
            }
        }

    @staticmethod
    def _text_query(text: str) -> dict[str, Any]:
        identity = BillReadScope.identity_query(text)
        if identity is not None:
            return identity
        should: list[dict[str, Any]] = [
            {
                "multi_match": {
                    "query": text,
                    "fields": [
                        "title^3",
                        "id",
                        "policy_area.name",
                        "sponsors.full_name",
                    ],
                }
            }
        ]
        lemma_query = try_lemmatize_query(text)
        if lemma_query:
            should.append(
                {"match": {"title_lemma": {"query": lemma_query, "boost": 2}}}
            )
        return {"bool": {"should": should, "minimum_should_match": 1}}

    @staticmethod
    def _summary(hit: dict[str, Any]) -> BillSummary | None:
        source: dict[str, Any] = hit.get("_source", {})
        bill_id = str(source.get("id") or hit.get("_id") or "")
        if not bill_id:
            return None
        return BillSummary(
            bill_id=bill_id,
            title=str(source.get("title") or bill_id),
            congress=source.get("congress"),
            bill_type=source.get("bill_type"),
            number=str(source["number"]) if source.get("number") is not None else None,
            chamber=source.get("origin_chamber") or source.get("chamber"),
            updated_at=source.get("update_date"),
        )

    def _relationship_counts(self, source: dict[str, Any]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for field in self._reads.bill_relationship_fields:
            value = source.get(field)
            if isinstance(value, dict) and value.get("count") is not None:
                counts[field] = int(value["count"])
            elif isinstance(value, list):
                counts[field] = len(value)
        return counts

    @staticmethod
    def _dict_list(source: dict[str, Any], field: str) -> list[dict[str, Any]]:
        value = source.get(field)
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

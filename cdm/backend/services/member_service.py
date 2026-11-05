from datetime import UTC, datetime
from typing import Any

from elasticsearch import Elasticsearch
from pydantic import AliasPath, BaseModel, Field

from cdm.backend.errors import EntityNotFoundError
from cdm.backend.services.search_service import SearchService
from cdm.config.query_reads import ActivityKind, QueryReadConfig
from cdm.contracts.api import (
    ActivityItem,
    MemberActivityItem,
    MemberActivityResponse,
    MemberDetail,
    MemberProfileResponse,
    MembersResponse,
    MemberSummary,
    MemberTerm,
)
from cdm.store.bill_scope import BillReadScope
from cdm.store.client import IncompleteSearchError, SearchCompletion
from cdm.store.opensearch import read_alias


def _terms(source: dict[str, Any]) -> list[dict[str, Any]]:
    raw_terms = source.get("terms") or {}
    if isinstance(raw_terms, dict):
        raw_terms = raw_terms.get("item") or []
    return raw_terms if isinstance(raw_terms, list) else []


def _congress_for_year(year: int) -> int:
    return (year - 1789) // 2 + 1


def _expand_terms(source: dict[str, Any]) -> list[MemberTerm]:
    """One row per Congress served; list-endpoint terms only carry years."""
    current_year = datetime.now(UTC).year
    state_name = source.get("state")
    rows: list[MemberTerm] = []
    for term in _terms(source):
        if not isinstance(term, dict):
            continue
        base = {
            "chamber": term.get("chamber"),
            "member_type": term.get("member_type"),
            "state_code": term.get("state_code"),
            "state_name": term.get("state_name") or state_name,
            "district": term.get("district"),
        }
        start, end = term.get("start_year"), term.get("end_year")
        if term.get("congress") or not start:
            rows.append(
                MemberTerm(
                    **base,
                    congress=term.get("congress"),
                    start_year=start,
                    end_year=end,
                )
            )
            continue
        # A term ending in an odd year ended in January, before that Congress began.
        last_year = current_year if not end else (end - 1 if end % 2 else end)
        first = _congress_for_year(start)
        last = max(first, _congress_for_year(last_year))
        for congress in range(first, last + 1):
            rows.append(
                MemberTerm(
                    **base,
                    congress=congress,
                    start_year=max(start, 1789 + 2 * (congress - 1)),
                    end_year=min(end, 1791 + 2 * (congress - 1)) if end else None,
                )
            )
    return rows


def _current_term(source: dict[str, Any]) -> dict[str, Any]:
    terms = _terms(source)
    if not terms:
        return {}
    current_year = datetime.now(UTC).year
    active = [
        term
        for term in terms
        if term.get("start_year", 0) <= current_year and not term.get("end_year")
    ]
    return active[-1] if active else terms[-1]


def _member_summary(source: dict[str, Any], fallback_id: str = "") -> MemberSummary:
    term = _current_term(source)
    bioguide_id = str(source.get("bioguide_id") or fallback_id)
    depiction = source.get("depiction")
    image_url = source.get("image_url")
    if not image_url and isinstance(depiction, dict):
        image_url = depiction.get("image_url")
    return MemberSummary(
        bioguide_id=bioguide_id,
        display_name=str(source.get("name") or source.get("full_name") or bioguide_id),
        party=str(source.get("party_name") or source.get("party") or "Unknown"),
        state=str(source.get("state") or source.get("state_code") or "Unknown"),
        chamber=term.get("chamber"),
        district=source.get("district"),
        term_start_year=term.get("start_year"),
        term_end_year=term.get("end_year"),
        image_url=image_url,
    )


def _member_detail(source: dict[str, Any], fallback_id: str = "") -> MemberDetail:
    summary = _member_summary(source, fallback_id)
    address = source.get("address_information")
    if not isinstance(address, dict):
        address = {}
    depiction = source.get("depiction")
    attribution = depiction.get("attribution") if isinstance(depiction, dict) else None
    leadership = source.get("leadership")
    party_history = source.get("party_history")
    terms = _expand_terms(source)
    return MemberDetail(
        **summary.model_dump(),
        honorific_name=source.get("honorific_name") or None,
        birth_year=str(source["birth_year"]) if source.get("birth_year") else None,
        death_year=str(source["death_year"]) if source.get("death_year") else None,
        official_website_url=source.get("official_website_url") or None,
        office_address=address.get("office_address") or None,
        phone_number=address.get("phone_number") or None,
        current_member=source.get("current_member"),
        leadership=leadership if isinstance(leadership, list) else [],
        party_history=party_history if isinstance(party_history, list) else [],
        terms=terms,
        image_attribution=attribution or None,
    )


def _member_link_query(
    bioguide_id: str, extra_filters: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "bool": {
            "filter": [
                *extra_filters,
                {
                    "bool": {
                        "should": [
                            {"term": {"sponsor_bioguide_ids": bioguide_id}},
                            {"term": {"cosponsor_bioguide_ids": bioguide_id}},
                        ],
                        "minimum_should_match": 1,
                    }
                },
            ]
        }
    }


def _activity_type(source: dict[str, Any], bioguide_id: str) -> str:
    return (
        "Sponsor"
        if bioguide_id in (source.get("sponsor_bioguide_ids") or [])
        else "Cosponsor"
    )


def _bill_activity_item(source: dict[str, Any], bioguide_id: str) -> MemberActivityItem:
    bill_id = str(source.get("id") or "")
    return MemberActivityItem(
        id=bill_id,
        document_type="bill",
        activity_type=_activity_type(source, bioguide_id),
        title=str(source.get("title") or "Untitled bill"),
        date=source.get("latest_action_date") or source.get("update_date"),
        congress=source.get("congress"),
        bill_id=bill_id,
    )


def _amendment_activity_item(
    source: dict[str, Any], bioguide_id: str
) -> MemberActivityItem:
    amended_bill = source.get("amended_bill") or {}
    label = f"{source.get('type') or 'Amendment'} {source.get('number') or ''}".strip()
    detail = (
        source.get("purpose")
        or source.get("description")
        or (f"to {amended_bill.get('title')}" if amended_bill.get("title") else "")
    )
    return MemberActivityItem(
        id=str(source.get("id") or ""),
        document_type="amendment",
        activity_type=_activity_type(source, bioguide_id),
        title=f"{label}: {detail}" if detail else label,
        date=source.get("submitted_date") or source.get("update_date"),
        congress=source.get("congress"),
        bill_id=amended_bill.get("id") or source.get("amended_bill_id"),
    )


class ActivityCount(BaseModel):
    doc_count: int


class ActivityTotals(BaseModel):
    counts: dict[ActivityKind, ActivityCount] = Field(
        validation_alias=AliasPath("aggregations", "counts", "buckets")
    )


class MemberService:
    def __init__(
        self,
        client: Elasticsearch,
        search: SearchService,
        reads: QueryReadConfig | None = None,
    ) -> None:
        self._client = client
        self._search = search
        self._reads = reads or QueryReadConfig()

    def list_members(
        self,
        query: str | None,
        state: str | None,
        chamber: str | None,
        party: str | None,
        page: int,
        limit: int,
    ) -> MembersResponse:
        offset = self._reads.offset(page, limit)
        for parameter, value in (
            ("query", query),
            ("state", state),
            ("chamber", chamber),
            ("party", party),
        ):
            if value:
                self._reads.text(value, parameter)
        filters: list[dict[str, Any]] = []
        if state:
            filters.append({"match": {"state": state.strip()}})
        if party:
            filters.append({"match": {"party_name": party.strip()}})
        if chamber:
            chamber_name = {
                "house": "House of Representatives",
                "senate": "Senate",
            }.get(chamber.strip().lower(), chamber.strip())
            filters.append({"match": {"terms.item.chamber": chamber_name}})
        query_body: dict[str, Any] = {"bool": {"filter": filters}}
        if query and query.strip():
            text_should: list[dict[str, Any]] = [
                {
                    "multi_match": {
                        "query": query.strip(),
                        "type": "cross_fields",
                        "operator": "and",
                        "fields": ["name^3", "full_name^3", "bioguide_id", "state"],
                    }
                }
            ]
            query_body["bool"]["must"] = [
                {"bool": {"should": text_should, "minimum_should_match": 1}}
            ]
        response = self._client.search(
            index=read_alias("member"),
            allow_partial_search_results=False,
            body={
                "from": offset,
                "size": limit,
                "track_total_hits": True,
                "_source": list(self._reads.member_fields),
                "query": query_body,
                "sort": [
                    {"_score": "desc"},
                    {"update_date": "desc"},
                    {"bioguide_id": "asc"},
                    {"id": "asc"},
                ],
            },
        )
        SearchCompletion.model_validate(response.body).require_complete()
        total = response.get("hits", {}).get("total", 0)
        if isinstance(total, dict):
            total = total.get("value", 0)
        members = [
            _member_summary(hit.get("_source", {}), str(hit.get("_id", "")))
            for hit in response.get("hits", {}).get("hits", [])
        ]
        return MembersResponse(
            members=members,
            total=int(total),
            page=page,
            limit=limit,
            max_result_window=self._reads.max_result_window,
        )

    def get_profile(self, bioguide_id: str) -> MemberProfileResponse:
        normalized_id = bioguide_id.strip().upper()
        response = self._client.search(
            index=read_alias("member"),
            allow_partial_search_results=False,
            body={
                "size": 25,
                "query": {
                    "bool": {
                        "should": [
                            {"term": {"bioguide_id": normalized_id}},
                            {"wildcard": {"id": f"*{normalized_id}"}},
                        ],
                        "minimum_should_match": 1,
                    }
                },
            },
        )
        SearchCompletion.model_validate(response.body).require_complete()
        hits = response.get("hits", {}).get("hits", [])
        if not hits:
            raise EntityNotFoundError(f"Member not found: {normalized_id}")

        source = max((hit.get("_source", {}) for hit in hits), key=self._richness)
        display_name = (
            source.get("name")
            or source.get("full_name")
            or source.get("direct_order_name")
        )
        if not display_name:
            matches = self._search.search_members(normalized_id, 1)
            display_name = matches[0].title if matches else normalized_id

        return MemberProfileResponse(
            member=_member_detail({**source, "name": display_name}, normalized_id),
            recent_activity=self._recent_activity(normalized_id),
        )

    def list_activity(
        self,
        bioguide_id: str,
        types: str | None = None,
        page: int = 1,
        limit: int = 25,
    ) -> MemberActivityResponse:
        """One bounded page, sorted by the displayed date then canonical id."""
        offset = self._reads.offset(page, limit)
        normalized_id = bioguide_id.strip().upper()
        selected = self._reads.selected(types, ActivityKind)
        response = self._client.search(
            index=[read_alias(kind) for kind in selected],
            allow_partial_search_results=False,
            body={
                "from": offset,
                "size": limit,
                "track_total_hits": True,
                "_source": list(self._reads.activity_fields),
                "runtime_mappings": {
                    "activity_date": {
                        "type": "date",
                        "script": self._reads.activity_date_script,
                    }
                },
                "query": _member_link_query(
                    normalized_id,
                    [
                        {
                            "bool": {
                                "should": [
                                    BillReadScope.query(),
                                    {"term": {"_index": read_alias("amendment")}},
                                ],
                                "minimum_should_match": 1,
                            },
                        }
                    ],
                ),
                "sort": [
                    {"activity_date": {"order": "desc", "missing": "_last"}},
                    {"id": "asc"},
                ],
                "aggs": {
                    "counts": {
                        "filters": {
                            "filters": {
                                kind.value: {"term": {"_index": read_alias(kind)}}
                                for kind in selected
                            }
                        }
                    }
                },
            },
        )
        SearchCompletion.model_validate(response.body).require_complete()
        counts = {
            kind.value: bucket.doc_count
            for kind, bucket in ActivityTotals.model_validate(
                response.body
            ).counts.items()
        }
        items: list[MemberActivityItem] = []
        for hit in response.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            try:
                kind = ActivityKind(str(source.get("id") or "").partition(":")[0])
            except ValueError as exc:
                raise IncompleteSearchError(
                    "Activity record has no canonical id"
                ) from exc
            parse = (
                _bill_activity_item
                if kind == ActivityKind.BILL
                else _amendment_activity_item
            )
            items.append(parse(source, normalized_id))
        return MemberActivityResponse(
            items=items,
            total=sum(counts.values()),
            counts=counts,
            page=page,
            limit=limit,
            max_result_window=self._reads.max_result_window,
        )

    def get_summaries(self, bioguide_ids: list[str]) -> dict[str, MemberSummary]:
        """Summaries for the given ids; ids with no member document are omitted."""
        if not bioguide_ids:
            return {}
        response = self._client.mget(
            index=read_alias("member"),
            ids=[f"member:{bioguide_id}" for bioguide_id in bioguide_ids],
        )
        summaries: dict[str, MemberSummary] = {}
        for doc in response["docs"]:
            if doc.get("found"):
                summary = _member_summary(doc["_source"])
                summaries[summary.bioguide_id] = summary
        return summaries

    @staticmethod
    def _richness(hit: dict[str, Any]) -> int:
        source = hit.get("_source", {})
        return sum(
            bool(source.get(field))
            for field in (
                "name",
                "full_name",
                "party_name",
                "state",
                "terms",
                "image_url",
            )
        )

    def _recent_activity(self, bioguide_id: str, limit: int = 20) -> list[ActivityItem]:
        self._reads.offset(1, limit)
        response = self._client.search(
            index=read_alias("bill"),
            allow_partial_search_results=False,
            body={
                "size": limit,
                "track_total_hits": False,
                "_source": list(self._reads.activity_fields),
                "query": _member_link_query(
                    bioguide_id, [BillReadScope.query()]
                ),
                "sort": [
                    {"update_date": {"order": "desc", "missing": "_last"}},
                    {"id": "asc"},
                ],
            },
        )
        SearchCompletion.model_validate(response.body).require_complete()
        activity: list[ActivityItem] = []
        for hit in response.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            sponsor_ids = source.get("sponsor_bioguide_ids") or []
            activity_type = "Sponsor" if bioguide_id in sponsor_ids else "Cosponsor"
            activity.append(
                ActivityItem(
                    bill_id=str(source.get("id") or hit.get("_id") or ""),
                    title=str(source.get("title") or "Untitled bill"),
                    activity_type=activity_type,
                    congress=int(source.get("congress") or 0),
                )
            )
        return activity

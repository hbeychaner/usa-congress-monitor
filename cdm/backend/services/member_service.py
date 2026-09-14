from datetime import UTC, datetime
from typing import Any

from cdm.contracts.api import (
    MemberActivityItem,
    MemberActivityResponse,
    MemberProfileResponse,
    MembersResponse,
    MemberSummary,
)
from cdm.store.client import get_opensearch_client
from cdm.store.opensearch import read_alias
from cdm.utils.lemmatize import try_lemmatize_query


def _terms(source: dict[str, Any]) -> list[dict[str, Any]]:
    raw_terms = source.get("terms") or {}
    if isinstance(raw_terms, dict):
        raw_terms = raw_terms.get("item") or []
    return raw_terms if isinstance(raw_terms, list) else []


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


def _recent_activity(bioguide_id: str, limit: int = 20) -> list[dict[str, Any]]:
    response = get_opensearch_client().search(
        index=read_alias("bill"),
        body={
            "size": limit,
            "track_total_hits": False,
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"source_type": "bill"}},
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
            },
            "sort": [{"update_date": {"order": "desc", "missing": "_last"}}],
        },
    )
    activity: list[dict[str, Any]] = []
    for hit in response.get("hits", {}).get("hits", []):
        source = hit.get("_source", {})
        sponsor_ids = source.get("sponsor_bioguide_ids") or []
        activity_type = "Sponsor" if bioguide_id in sponsor_ids else "Cosponsor"
        activity.append({
            "bill_id": str(source.get("id") or hit.get("_id") or ""),
            "title": str(source.get("title") or "Untitled bill"),
            "activity_type": activity_type,
            "congress": int(source.get("congress") or 0),
        })
    return activity


def list_members(
    query: str | None,
    state: str | None,
    chamber: str | None,
    party: str | None,
    page: int,
    limit: int,
) -> MembersResponse:
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
                    "fields": ["name^3", "full_name^3", "bioguide_id", "state"],
                }
            }
        ]
        lemma_query = try_lemmatize_query(query.strip())
        if lemma_query:
            text_should.append(
                {"match": {"name_lemma": {"query": lemma_query, "boost": 2}}}
            )
        query_body["bool"]["must"] = [
            {"bool": {"should": text_should, "minimum_should_match": 1}}
        ]
    response = get_opensearch_client().search(
        index=read_alias("member"),
        body={
            "from": (page - 1) * limit,
            "size": limit,
            "track_total_hits": True,
            "query": query_body,
            "sort": [{"update_date": "desc"}, {"bioguide_id": "asc"}],
        },
    )
    total = response.get("hits", {}).get("total", 0)
    if isinstance(total, dict):
        total = total.get("value", 0)
    members = [
        _member_summary(hit.get("_source", {}), str(hit.get("_id", "")))
        for hit in response.get("hits", {}).get("hits", [])
    ]
    return MembersResponse(members=members, total=int(total), page=page, limit=limit)


def get_member_profile(bioguide_id: str) -> MemberProfileResponse:
    normalized_id = bioguide_id.strip().upper()
    response = get_opensearch_client().search(
        index=read_alias("member"),
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
    hits = response.get("hits", {}).get("hits", [])
    if not hits:
        raise ValueError(f"Member not found: {normalized_id}")

    def richness(hit: dict) -> int:
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

    source = max((hit.get("_source", {}) for hit in hits), key=richness)
    display_name = (
        source.get("name") or source.get("full_name") or source.get("direct_order_name")
    )
    if not display_name:
        from cdm.backend.services.search_service import search_entities

        matches = search_entities(normalized_id, "member", 1).results
        display_name = matches[0].title if matches else normalized_id
    return MemberProfileResponse(
        member=_member_summary({**source, "name": display_name}, normalized_id),
        recent_activity=_recent_activity(normalized_id),
        topics=[],
    )


def _member_link_query(bioguide_id: str, extra_filters: list[dict[str, Any]]) -> dict[str, Any]:
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
    return "Sponsor" if bioguide_id in (source.get("sponsor_bioguide_ids") or []) else "Cosponsor"


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


def _amendment_activity_item(source: dict[str, Any], bioguide_id: str) -> MemberActivityItem:
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


# One entry per activity source: (resource alias, extra filters, sort field, parser).
_ACTIVITY_SOURCES: dict[str, dict[str, Any]] = {
    "bill": {
        "resource": "bill",
        "filters": [{"term": {"source_type": "bill"}}],
        "sort": "update_date",
        "fields": [
            "id", "title", "congress", "update_date", "latest_action_date",
            "sponsor_bioguide_ids",
        ],
        "parse": _bill_activity_item,
    },
    "amendment": {
        "resource": "amendment",
        "filters": [],
        "sort": "submitted_date",
        "fields": [
            "id", "type", "number", "congress", "purpose", "description",
            "submitted_date", "update_date", "amended_bill", "amended_bill_id",
            "sponsor_bioguide_ids",
        ],
        "parse": _amendment_activity_item,
    },
}


def list_member_activity(
    bioguide_id: str,
    types: str | None = None,
    page: int = 1,
    limit: int = 25,
) -> MemberActivityResponse:
    """Merged, date-sorted member activity across all linked document types."""
    normalized_id = bioguide_id.strip().upper()
    selected = [t.strip().lower() for t in (types or "").split(",") if t.strip()]
    selected = [t for t in selected if t in _ACTIVITY_SOURCES] or list(_ACTIVITY_SOURCES)

    client = get_opensearch_client()
    fetch_size = min(page * limit, 10_000)
    items: list[MemberActivityItem] = []
    counts: dict[str, int] = {}
    for doc_type in selected:
        spec = _ACTIVITY_SOURCES[doc_type]
        response = client.search(
            index=read_alias(spec["resource"]),
            body={
                "size": fetch_size,
                "track_total_hits": True,
                "_source": spec["fields"],
                "query": _member_link_query(normalized_id, spec["filters"]),
                "sort": [{spec["sort"]: {"order": "desc", "missing": "_last"}}],
            },
        )
        hits = response.get("hits", {})
        total = hits.get("total", 0)
        counts[doc_type] = total.get("value", 0) if isinstance(total, dict) else int(total)
        for hit in hits.get("hits", []):
            item = spec["parse"](hit.get("_source", {}), normalized_id)
            if item.id:
                items.append(item)

    items.sort(key=lambda item: item.date or "", reverse=True)
    start = (page - 1) * limit
    return MemberActivityResponse(
        items=items[start : start + limit],
        total=sum(counts.values()),
        counts=counts,
        page=page,
        limit=limit,
    )

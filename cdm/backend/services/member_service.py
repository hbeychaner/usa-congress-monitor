from datetime import UTC, datetime
from typing import Any

from cdm.contracts.api import MemberProfileResponse, MembersResponse, MemberSummary
from cdm.store.client import get_opensearch_client
from cdm.store.opensearch import read_alias


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
        query_body["bool"]["must"] = [
            {
                "multi_match": {
                    "query": query.strip(),
                    "fields": ["name^3", "full_name^3", "bioguide_id", "state"],
                }
            }
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

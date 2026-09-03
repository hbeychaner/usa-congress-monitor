"""OpenSearch-backed bill listing services."""

from __future__ import annotations

from typing import Any

from cdm.contracts.api import BillDetail, BillDetailResponse, BillsResponse, BillSummary
from cdm.store.client import get_opensearch_client
from cdm.store.opensearch import read_alias


def list_recent_bills(
    limit: int = 50,
    page: int = 1,
    query: str | None = None,
    congress: int | None = None,
    bill_type: str | None = None,
    chamber: str | None = None,
) -> BillsResponse:
    """Return the most recently updated bills from the legislation read alias."""
    client = get_opensearch_client()
    filters: list[dict[str, Any]] = [{"term": {"source_type": "bill"}}]
    if congress is not None:
        filters.append({"term": {"congress": congress}})
    if bill_type:
        filters.append({"wildcard": {"id": f"bill:*:{bill_type.lower()}:*"}})
    if chamber:
        filters.append({"term": {"origin_chamber": chamber}})
    search_query: dict[str, Any] = {"bool": {"filter": filters}}
    if query and query.strip():
        search_query["bool"]["must"] = [
            {
                "multi_match": {
                    "query": query.strip(),
                    "fields": [
                        "title^3",
                        "id",
                        "policy_area.name",
                        "sponsors.full_name",
                    ],
                }
            }
        ]
    response = client.search(
        index=read_alias("bill"),
        body={
            "from": (page - 1) * limit,
            "size": limit,
            "track_total_hits": True,
            "query": search_query,
            "sort": [{"update_date": {"order": "desc", "missing": "_last"}}],
        },
    )
    hits = response.get("hits", {})
    total = hits.get("total", 0)
    if isinstance(total, dict):
        total = total.get("value", 0)
    bills: list[BillSummary] = []
    for hit in hits.get("hits", []):
        source: dict[str, Any] = hit.get("_source", {})
        bill_id = str(source.get("id") or hit.get("_id") or "")
        if not bill_id:
            continue
        bills.append(
            BillSummary(
                bill_id=bill_id,
                title=str(source.get("title") or bill_id),
                congress=source.get("congress"),
                bill_type=source.get("bill_type"),
                number=str(source["number"])
                if source.get("number") is not None
                else None,
                chamber=source.get("origin_chamber") or source.get("chamber"),
                updated_at=source.get("update_date"),
            )
        )
    return BillsResponse(bills=bills, total=int(total), page=page, limit=limit)


def get_bill(bill_id: str) -> BillDetailResponse:
    """Return one bill document from the OpenSearch read alias."""
    normalized_id = bill_id.strip()
    response = get_opensearch_client().get(index=read_alias("bill"), id=normalized_id)
    source: dict[str, Any] = response.get("_source", {})
    if source.get("source_type") != "bill":
        raise ValueError(f"Bill not found: {normalized_id}")

    relationships: dict[str, int] = {}
    for field in (
        "actions",
        "amendments",
        "committees",
        "cosponsors",
        "summaries",
        "titles",
        "text_versions",
    ):
        value = source.get(field)
        if isinstance(value, dict) and value.get("count") is not None:
            relationships[field] = int(value["count"])
        elif isinstance(value, list):
            relationships[field] = len(value)

    policy_area = source.get("policy_area")
    if isinstance(policy_area, dict):
        policy_area = policy_area.get("name")
    sponsors = source.get("sponsors")
    laws = source.get("laws")
    return BillDetailResponse(
        bill=BillDetail(
            bill_id=str(source.get("id") or normalized_id),
            title=str(source.get("title") or normalized_id),
            congress=source.get("congress"),
            bill_type=source.get("type"),
            number=str(source["number"]) if source.get("number") is not None else None,
            origin_chamber=source.get("origin_chamber"),
            origin_chamber_code=source.get("origin_chamber_code"),
            introduced_date=source.get("introduced_date"),
            update_date=source.get("update_date"),
            update_date_including_text=source.get("update_date_including_text"),
            latest_action=source.get("latest_action"),
            policy_area=policy_area,
            sponsors=sponsors if isinstance(sponsors, list) else [],
            subjects=source.get("subjects")
            if isinstance(source.get("subjects"), dict)
            else None,
            laws=laws if isinstance(laws, list) else [],
            constitutional_authority_statement_text=source.get(
                "constitutional_authority_statement_text"
            ),
            full_text=source.get("full_text") or None,
            relationship_counts=relationships,
        )
    )

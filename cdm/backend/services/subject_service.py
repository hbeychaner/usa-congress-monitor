"""Aggregations over the human-annotated CRS subject metadata on bills.

``subjects.legislative_subjects.name`` (nested) and ``policy_area.name`` are
keyword fields curated by the Congressional Research Service — a labeled
complement to the unsupervised BERTopic output.
"""

from __future__ import annotations

from typing import Any

from elasticsearch import NotFoundError

from cdm.contracts.api import (
    PolicyAreaTrendPoint,
    PolicyAreaTrendSeries,
    PolicyAreaTrendsResponse,
    SubjectCount,
    SubjectsResponse,
    TopicItem,
)
from cdm.store.client import get_opensearch_client
from cdm.store.opensearch import read_alias

_SUBJECTS_PATH = "subjects.legislative_subjects"
_SUBJECT_FIELD = f"{_SUBJECTS_PATH}.name"
_POLICY_AREA_FIELD = "policy_area.name"


def _subject_aggs(size: int) -> dict[str, Any]:
    return {
        "subjects": {
            "nested": {"path": _SUBJECTS_PATH},
            "aggs": {"names": {"terms": {"field": _SUBJECT_FIELD, "size": size}}},
        },
        "policy_areas": {"terms": {"field": _POLICY_AREA_FIELD, "size": size}},
    }


def _aggregate(filters: list[dict[str, Any]], size: int) -> dict[str, Any] | None:
    client = get_opensearch_client()
    try:
        return client.search(
            index=read_alias("bill"),
            body={
                "size": 0,
                "track_total_hits": True,
                "query": {"bool": {"filter": filters}},
                "aggs": _subject_aggs(size),
            },
        )
    except NotFoundError:
        return None


def _buckets(response: dict[str, Any] | None, *path: str) -> list[dict[str, Any]]:
    node: Any = (response or {}).get("aggregations") or {}
    for key in path:
        node = node.get(key) or {}
    return node.get("buckets") or []


def list_subjects(congress: int | None = None, size: int = 100) -> SubjectsResponse:
    """Most common legislative subjects and policy areas across bills."""
    filters: list[dict[str, Any]] = [{"term": {"source_type": "bill"}}]
    if congress is not None:
        filters.append({"term": {"congress": congress}})
    response = _aggregate(filters, size)
    total = ((response or {}).get("hits", {}).get("total") or {}).get("value", 0)
    return SubjectsResponse(
        subjects=[
            SubjectCount(name=str(b["key"]), count=int(b["doc_count"]))
            for b in _buckets(response, "subjects", "names")
        ],
        policy_areas=[
            SubjectCount(name=str(b["key"]), count=int(b["doc_count"]))
            for b in _buckets(response, "policy_areas")
        ],
        total_bills=int(total),
    )


def list_policy_area_trends(
    *, size: int = 10, start_year: int | None = None
) -> PolicyAreaTrendsResponse:
    """Bills per year for the most common CRS policy areas.

    Returns EMM-style regular series: every series covers the same contiguous
    year range, zero-filled, so line charts get a uniform time grid.
    """
    filters: list[dict[str, Any]] = [
        {"term": {"source_type": "bill"}},
        {"exists": {"field": "introduced_date"}},
    ]
    if start_year is not None:
        filters.append({"range": {"introduced_date": {"gte": f"{start_year}-01-01"}}})
    client = get_opensearch_client()
    try:
        response = client.search(
            index=read_alias("bill"),
            body={
                "size": 0,
                "track_total_hits": True,
                "query": {"bool": {"filter": filters}},
                "aggs": {
                    "areas": {
                        "terms": {"field": _POLICY_AREA_FIELD, "size": size},
                        "aggs": {
                            "per_year": {
                                "date_histogram": {
                                    "field": "introduced_date",
                                    "calendar_interval": "year",
                                    "format": "yyyy",
                                }
                            }
                        },
                    }
                },
            },
        )
    except NotFoundError:
        return PolicyAreaTrendsResponse()

    raw: dict[str, tuple[int, dict[int, int]]] = {}
    years: set[int] = set()
    for bucket in _buckets(response, "areas"):
        counts: dict[int, int] = {}
        for year_bucket in (bucket.get("per_year") or {}).get("buckets") or []:
            year = int(year_bucket["key_as_string"])
            counts[year] = int(year_bucket["doc_count"])
            years.add(year)
        raw[str(bucket["key"])] = (int(bucket["doc_count"]), counts)
    if not years:
        return PolicyAreaTrendsResponse()

    grid = range(min(years), max(years) + 1)
    total = ((response or {}).get("hits", {}).get("total") or {}).get("value", 0)
    return PolicyAreaTrendsResponse(
        series=[
            PolicyAreaTrendSeries(
                name=name,
                total=area_total,
                points=[
                    PolicyAreaTrendPoint(year=year, count=counts.get(year, 0))
                    for year in grid
                ],
            )
            for name, (area_total, counts) in raw.items()
        ],
        total_bills=int(total),
    )


def member_subject_items(
    bioguide_id: str, size: int = 25
) -> tuple[list[TopicItem], list[TopicItem]]:
    """(legislative subjects, policy areas) as weighted items for one member."""
    filters: list[dict[str, Any]] = [
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
    response = _aggregate(filters, size)

    def items(buckets: list[dict[str, Any]]) -> list[TopicItem]:
        total = sum(int(b["doc_count"]) for b in buckets)
        if not total:
            return []
        return [
            TopicItem(label=str(b["key"]), weight=round(int(b["doc_count"]) / total, 4))
            for b in buckets
        ]

    return (
        items(_buckets(response, "subjects", "names")),
        items(_buckets(response, "policy_areas")),
    )

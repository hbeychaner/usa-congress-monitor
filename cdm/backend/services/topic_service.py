"""Read topic-model output from the analysis index for API responses.

All queries target the latest ``model_version`` in ``congress-analysis-topics``
(written by ``scripts/train_topic_model.py``). Every function degrades to an
empty response when the index or a trained model does not exist yet.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from elasticsearch import NotFoundError

from cdm.contracts.api import (
    BillTopicsResponse,
    MemberTopicsResponse,
    MemberTopicTrendPoint,
    TopicAssignmentItem,
    TopicBill,
    TopicDetailResponse,
    TopicItem,
    TopicsResponse,
    TopicSummary,
    TopicTrendPoint,
    TopicTrendSeries,
    TopicTrendsResponse,
)
from cdm.store.client import get_opensearch_client
from cdm.store.opensearch import read_alias

ANALYSIS_INDEX = "congress-analysis-topics"
_OUTLIER_TOPIC_ID = -1
_TERMS_CHUNK = 1024


def topic_label(name: str | None, topic_id: int) -> str:
    """Human-friendly label from a BERTopic name like ``5_health_care``."""
    if topic_id == _OUTLIER_TOPIC_ID:
        return "Uncategorized"
    if name:
        _, _, words = name.partition("_")
        if words:
            return words.replace("_", " ")
        return name
    return f"Topic {topic_id}"


def _search(body: dict[str, Any]) -> dict[str, Any] | None:
    client = get_opensearch_client()
    try:
        return client.search(index=ANALYSIS_INDEX, body=body)
    except NotFoundError:
        return None


def _hits(response: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not response:
        return []
    return response.get("hits", {}).get("hits", [])


def _latest_model_version() -> tuple[str | None, str | None]:
    response = _search({
        "size": 1,
        "query": {"term": {"kind": "topic"}},
        "sort": [{"trained_at": {"order": "desc"}}],
        "_source": ["model_version", "trained_at"],
    })
    hits = _hits(response)
    if not hits:
        return None, None
    source = hits[0].get("_source", {})
    return source.get("model_version"), source.get("trained_at")


def _topic_summaries(model_version: str) -> dict[int, TopicSummary]:
    response = _search({
        "size": 1000,
        "query": {
            "bool": {
                "filter": [
                    {"term": {"kind": "topic"}},
                    {"term": {"model_version": model_version}},
                ]
            }
        },
    })
    summaries: dict[int, TopicSummary] = {}
    for hit in _hits(response):
        source = hit.get("_source", {})
        topic_id = int(source.get("topic_id", _OUTLIER_TOPIC_ID))
        summaries[topic_id] = TopicSummary(
            topic_id=topic_id,
            name=str(source.get("name") or ""),
            label=topic_label(source.get("name"), topic_id),
            size=int(source.get("size") or 0),
            top_words=[str(word) for word in source.get("top_words") or []],
        )
    return summaries


def list_topics() -> TopicsResponse:
    """All topics from the latest trained model, largest first."""
    model_version, trained_at = _latest_model_version()
    if not model_version:
        return TopicsResponse(topics=[])
    topics = [
        topic
        for topic in _topic_summaries(model_version).values()
        if topic.topic_id != _OUTLIER_TOPIC_ID
    ]
    topics.sort(key=lambda topic: topic.size, reverse=True)
    return TopicsResponse(
        topics=topics, model_version=model_version, trained_at=trained_at
    )


def list_topic_trends(*, size: int = 8) -> TopicTrendsResponse:
    """Time series for the largest topics, EMM-dashboard style."""
    model_version, _ = _latest_model_version()
    if not model_version:
        return TopicTrendsResponse(series=[])
    summaries = _topic_summaries(model_version)
    top = sorted(
        (topic for topic in summaries.values() if topic.topic_id != _OUTLIER_TOPIC_ID),
        key=lambda topic: topic.size,
        reverse=True,
    )[:size]
    top_ids = [topic.topic_id for topic in top]
    response = _search({
        "size": 10000,
        "query": {
            "bool": {
                "filter": [
                    {"term": {"kind": "topic_over_time"}},
                    {"term": {"model_version": model_version}},
                    {"terms": {"topic_id": top_ids}},
                ]
            }
        },
        "sort": [{"timestamp": {"order": "asc"}}],
    })
    points: dict[int, list[TopicTrendPoint]] = defaultdict(list)
    for hit in _hits(response):
        source = hit.get("_source", {})
        topic_id = int(source.get("topic_id", _OUTLIER_TOPIC_ID))
        points[topic_id].append(
            TopicTrendPoint(
                timestamp=str(source.get("timestamp") or ""),
                frequency=int(source.get("frequency") or 0),
                words=source.get("words"),
            )
        )
    series = [
        TopicTrendSeries(
            topic_id=topic.topic_id,
            label=topic.label,
            points=points.get(topic.topic_id, []),
        )
        for topic in top
        if points.get(topic.topic_id)
    ]
    return TopicTrendsResponse(series=series, model_version=model_version)


def get_topic(topic_id: int, *, top_bills: int = 20) -> TopicDetailResponse | None:
    """One topic with its time trend and highest-probability bills."""
    model_version, _ = _latest_model_version()
    if not model_version:
        return None
    topic = _topic_summaries(model_version).get(topic_id)
    if topic is None:
        return None

    trend_response = _search({
        "size": 500,
        "query": {
            "bool": {
                "filter": [
                    {"term": {"kind": "topic_over_time"}},
                    {"term": {"model_version": model_version}},
                    {"term": {"topic_id": topic_id}},
                ]
            }
        },
        "sort": [{"timestamp": {"order": "asc"}}],
    })
    trend = [
        TopicTrendPoint(
            timestamp=str(source.get("timestamp")),
            frequency=int(source.get("frequency") or 0),
            words=source.get("words"),
        )
        for hit in _hits(trend_response)
        if (source := hit.get("_source", {})).get("timestamp")
    ]

    assignment_response = _search({
        "size": top_bills,
        "query": {
            "bool": {
                "filter": [
                    {"term": {"kind": "assignment"}},
                    {"term": {"model_version": model_version}},
                    {"term": {"topic_id": topic_id}},
                ]
            }
        },
        "sort": [{"probability": {"order": "desc"}}],
        "_source": ["doc_id", "probability"],
    })
    assignments = [
        (str(source.get("doc_id")), float(source.get("probability") or 0.0))
        for hit in _hits(assignment_response)
        if (source := hit.get("_source", {})).get("doc_id")
    ]
    titles = _bill_titles([doc_id for doc_id, _ in assignments])
    bills = [
        TopicBill(bill_id=doc_id, title=titles.get(doc_id), probability=probability)
        for doc_id, probability in assignments
    ]
    return TopicDetailResponse(
        topic=topic, model_version=model_version, trend=trend, top_bills=bills
    )


def _bill_titles(bill_ids: list[str]) -> dict[str, str]:
    if not bill_ids:
        return {}
    client = get_opensearch_client()
    try:
        response = client.mget(
            index=read_alias("bill"),
            body={"ids": bill_ids},
            _source=["title"],
        )
    except NotFoundError:
        return {}
    return {
        doc["_id"]: str(doc["_source"].get("title") or "")
        for doc in response.get("docs", [])
        if doc.get("found") and doc.get("_source")
    }


def get_bill_topics(bill_id: str) -> BillTopicsResponse:
    """Topic assignments for one bill under the latest model."""
    model_version, _ = _latest_model_version()
    if not model_version:
        return BillTopicsResponse(bill_id=bill_id)
    response = _search({
        "size": 10,
        "query": {
            "bool": {
                "filter": [
                    {"term": {"kind": "assignment"}},
                    {"term": {"model_version": model_version}},
                    {"term": {"doc_id": bill_id}},
                ]
            }
        },
        "sort": [{"probability": {"order": "desc"}}],
    })
    summaries = _topic_summaries(model_version)
    topics = []
    for hit in _hits(response):
        source = hit.get("_source", {})
        topic_id = int(source.get("topic_id", _OUTLIER_TOPIC_ID))
        if topic_id == _OUTLIER_TOPIC_ID:
            continue
        summary = summaries.get(topic_id)
        topics.append(
            TopicAssignmentItem(
                topic_id=topic_id,
                label=summary.label if summary else f"Topic {topic_id}",
                probability=float(source.get("probability") or 0.0),
            )
        )
    return BillTopicsResponse(
        bill_id=bill_id, topics=topics, model_version=model_version
    )


def _member_bill_dates(bioguide_id: str) -> dict[str, str | None]:
    """Bill id → introduced date for bills the member sponsored/cosponsored."""
    client = get_opensearch_client()
    try:
        response = client.search(
            index=read_alias("bill"),
            body={
                "size": 5000,
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"source_type": "bill"}},
                            {
                                "bool": {
                                    "should": [
                                        {"term": {"sponsor_bioguide_ids": bioguide_id}},
                                        {
                                            "term": {
                                                "cosponsor_bioguide_ids": bioguide_id
                                            }
                                        },
                                    ],
                                    "minimum_should_match": 1,
                                }
                            },
                        ]
                    }
                },
                "_source": ["introduced_date"],
            },
        )
    except NotFoundError:
        return {}
    return {
        hit["_id"]: (hit.get("_source") or {}).get("introduced_date")
        for hit in response.get("hits", {}).get("hits", [])
    }


def _member_assignments(
    bill_ids: list[str], model_version: str
) -> list[tuple[str, int]]:
    """(bill_id, topic_id) pairs for the member's bills under *model_version*."""
    pairs: list[tuple[str, int]] = []
    for start in range(0, len(bill_ids), _TERMS_CHUNK):
        chunk = bill_ids[start : start + _TERMS_CHUNK]
        response = _search({
            "size": len(chunk),
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"kind": "assignment"}},
                        {"term": {"model_version": model_version}},
                        {"terms": {"doc_id": chunk}},
                    ]
                }
            },
            "_source": ["doc_id", "topic_id"],
        })
        for hit in _hits(response):
            source = hit.get("_source", {})
            topic_id = int(source.get("topic_id", _OUTLIER_TOPIC_ID))
            if topic_id != _OUTLIER_TOPIC_ID and source.get("doc_id"):
                pairs.append((str(source["doc_id"]), topic_id))
    return pairs


def _quarter(date: str) -> str:
    year, month = date[:4], date[5:7]
    quarter = (int(month) - 1) // 3 + 1 if month.isdigit() else 1
    return f"{year}-Q{quarter}"


def get_member_topics(bioguide_id: str) -> MemberTopicsResponse:
    """Topic totals and per-quarter trend for a member's sponsored bills."""
    from cdm.backend.services.subject_service import member_subject_items

    subjects, policy_areas = member_subject_items(bioguide_id)
    model_version, _ = _latest_model_version()
    if not model_version:
        return MemberTopicsResponse(
            bioguide_id=bioguide_id, subjects=subjects, policy_areas=policy_areas
        )
    bill_dates = _member_bill_dates(bioguide_id)
    if not bill_dates:
        return MemberTopicsResponse(
            bioguide_id=bioguide_id,
            model_version=model_version,
            subjects=subjects,
            policy_areas=policy_areas,
        )
    pairs = _member_assignments(list(bill_dates), model_version)
    if not pairs:
        return MemberTopicsResponse(
            bioguide_id=bioguide_id,
            model_version=model_version,
            subjects=subjects,
            policy_areas=policy_areas,
        )
    summaries = _topic_summaries(model_version)

    totals: Counter[int] = Counter(topic_id for _, topic_id in pairs)
    total_count = sum(totals.values())
    topics = [
        TopicItem(
            label=(
                summaries[topic_id].label
                if topic_id in summaries
                else f"Topic {topic_id}"
            ),
            weight=round(count / total_count, 4),
        )
        for topic_id, count in totals.most_common()
    ]

    buckets: dict[tuple[str, int], int] = defaultdict(int)
    for bill_id, topic_id in pairs:
        date = bill_dates.get(bill_id)
        if date:
            buckets[(_quarter(str(date)), topic_id)] += 1
    trend = [
        MemberTopicTrendPoint(
            period=period,
            topic_id=topic_id,
            label=(
                summaries[topic_id].label
                if topic_id in summaries
                else f"Topic {topic_id}"
            ),
            count=count,
        )
        for (period, topic_id), count in sorted(buckets.items())
    ]
    return MemberTopicsResponse(
        bioguide_id=bioguide_id,
        topics=topics,
        trend=trend,
        model_version=model_version,
        subjects=subjects,
        policy_areas=policy_areas,
    )

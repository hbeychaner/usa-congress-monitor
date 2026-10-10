"""Read topic-model output from the analysis index for API responses.

All queries target the latest ``model_version`` in the analysis index (written by
``scripts/train_topic_model.py``). Every method degrades to an empty response when
the index or a trained model does not exist yet.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from elasticsearch import NotFoundError

from cdm.backend.services.subject_service import SubjectService
from cdm.contracts.api import (
    BillTopicsResponse,
    MemberTopicsResponse,
    MemberTopicTrendPoint,
    MetasubjectDetailResponse,
    MetasubjectsResponse,
    MetasubjectSummary,
    MetasubjectTrendSeries,
    MetasubjectTrendsResponse,
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
from cdm.store.opensearch import read_alias
from cdm.utils.topic_terms import dedupe_terms, keyword_label

_OUTLIER_TOPIC_ID = -1
_TERMS_CHUNK = 1024
_METASUBJECT_KIND = "metasubject"
_METASUBJECT_TREND_KIND = "metasubject_over_time"
_METASUBJECT_LIMIT = 100
_METASUBJECT_TREND_LIMIT = 10000


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


def _quarter(date: str) -> str:
    year, month = date[:4], date[5:7]
    quarter = (int(month) - 1) // 3 + 1 if month.isdigit() else 1
    return f"{year}-Q{quarter}"


class TopicService:
    def __init__(self, client: Any, analysis_index: str, subjects: SubjectService) -> None:
        self._client = client
        self._index = analysis_index
        self._subjects = subjects

    def latest_model_version(self) -> tuple[str | None, str | None]:
        response = self._search({
            "size": 1,
            "query": {"term": {"kind": "topic"}},
            "sort": [{"trained_at": {"order": "desc"}}],
            "_source": ["model_version", "trained_at"],
        })
        hits = self._hits(response)
        if not hits:
            return None, None
        source = hits[0].get("_source", {})
        return source.get("model_version"), source.get("trained_at")

    def topic_summaries(self, model_version: str) -> dict[int, TopicSummary]:
        response = self._search({
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
        for hit in self._hits(response):
            source = hit.get("_source", {})
            topic_id = int(source.get("topic_id", _OUTLIER_TOPIC_ID))
            stored_label = str(source.get("label") or "").strip()
            top_words = dedupe_terms(
                str(word) for word in source.get("top_words") or []
            )
            keywords = keyword_label(top_words)
            summaries[topic_id] = TopicSummary(
                topic_id=topic_id,
                name=str(source.get("name") or ""),
                label=stored_label
                or (keywords if topic_id != _OUTLIER_TOPIC_ID and keywords else None)
                or topic_label(source.get("name"), topic_id),
                size=int(source.get("size") or 0),
                top_words=top_words,
                metasubject_id=source.get("metasubject_id"),
            )
        return summaries

    def member_assignments(
        self, bill_ids: list[str], model_version: str
    ) -> list[tuple[str, int]]:
        """(bill_id, topic_id) pairs for the member's bills under *model_version*."""
        pairs: list[tuple[str, int]] = []
        for start in range(0, len(bill_ids), _TERMS_CHUNK):
            chunk = bill_ids[start : start + _TERMS_CHUNK]
            response = self._search({
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
            for hit in self._hits(response):
                source = hit.get("_source", {})
                topic_id = int(source.get("topic_id", _OUTLIER_TOPIC_ID))
                if topic_id != _OUTLIER_TOPIC_ID and source.get("doc_id"):
                    pairs.append((str(source["doc_id"]), topic_id))
        return pairs

    def list_metasubjects(self) -> MetasubjectsResponse:
        """Metasubjects of the latest trained model, largest first."""
        model_version, _ = self.latest_model_version()
        if not model_version:
            return MetasubjectsResponse(metasubjects=[])
        return MetasubjectsResponse(
            metasubjects=list(self._metasubject_summaries(model_version).values()),
            model_version=model_version,
        )

    def list_metasubject_trends(self) -> MetasubjectTrendsResponse:
        """Quarterly bill counts for every metasubject."""
        model_version, _ = self.latest_model_version()
        if not model_version:
            return MetasubjectTrendsResponse(series=[])
        points = self._metasubject_points(model_version)
        series = [
            MetasubjectTrendSeries(
                metasubject_id=group.metasubject_id,
                label=group.name,
                points=points[group.metasubject_id],
            )
            for group in self._metasubject_summaries(model_version).values()
            if points.get(group.metasubject_id)
        ]
        return MetasubjectTrendsResponse(series=series, model_version=model_version)

    def get_metasubject(self, metasubject_id: int) -> MetasubjectDetailResponse | None:
        """One metasubject with its member topics and quarterly trend."""
        model_version, _ = self.latest_model_version()
        if not model_version:
            return None
        group = self._metasubject_summaries(model_version).get(metasubject_id)
        if group is None:
            return None
        topics = [
            topic
            for topic in self.topic_summaries(model_version).values()
            if topic.metasubject_id == metasubject_id
        ]
        topics.sort(key=lambda topic: topic.size, reverse=True)
        trend = self._metasubject_points(model_version, [metasubject_id]).get(
            metasubject_id, []
        )
        return MetasubjectDetailResponse(
            metasubject=group, topics=topics, trend=trend, model_version=model_version
        )

    def list_topics(self) -> TopicsResponse:
        """All topics from the latest trained model, largest first."""
        model_version, trained_at = self.latest_model_version()
        if not model_version:
            return TopicsResponse(topics=[])
        topics = [
            topic
            for topic in self.topic_summaries(model_version).values()
            if topic.topic_id != _OUTLIER_TOPIC_ID
        ]
        topics.sort(key=lambda topic: topic.size, reverse=True)
        return TopicsResponse(
            topics=topics, model_version=model_version, trained_at=trained_at
        )

    def list_topic_trends(self, *, size: int = 8) -> TopicTrendsResponse:
        """Time series for the largest topics, EMM-dashboard style."""
        model_version, _ = self.latest_model_version()
        if not model_version:
            return TopicTrendsResponse(series=[])
        summaries = self.topic_summaries(model_version)
        top = sorted(
            (
                topic
                for topic in summaries.values()
                if topic.topic_id != _OUTLIER_TOPIC_ID
            ),
            key=lambda topic: topic.size,
            reverse=True,
        )[:size]
        top_ids = [topic.topic_id for topic in top]
        response = self._search({
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
        for hit in self._hits(response):
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

    def get_topic(
        self, topic_id: int, *, top_bills: int = 20
    ) -> TopicDetailResponse | None:
        """One topic with its time trend and highest-probability bills."""
        model_version, _ = self.latest_model_version()
        if not model_version:
            return None
        topic = self.topic_summaries(model_version).get(topic_id)
        if topic is None:
            return None

        trend_response = self._search({
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
            for hit in self._hits(trend_response)
            if (source := hit.get("_source", {})).get("timestamp")
        ]

        assignment_response = self._search({
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
            for hit in self._hits(assignment_response)
            if (source := hit.get("_source", {})).get("doc_id")
        ]
        titles = self._bill_titles([doc_id for doc_id, _ in assignments])
        bills = [
            TopicBill(bill_id=doc_id, title=titles.get(doc_id), probability=probability)
            for doc_id, probability in assignments
        ]
        return TopicDetailResponse(
            topic=topic, model_version=model_version, trend=trend, top_bills=bills
        )

    def get_bill_topics(self, bill_id: str) -> BillTopicsResponse:
        """Topic assignments for one bill under the latest model."""
        model_version, _ = self.latest_model_version()
        if not model_version:
            return BillTopicsResponse(bill_id=bill_id)
        response = self._search({
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
        summaries = self.topic_summaries(model_version)
        topics = []
        for hit in self._hits(response):
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

    def get_member_topics(self, bioguide_id: str) -> MemberTopicsResponse:
        """Topic totals and per-quarter trend for a member's sponsored bills."""
        subjects, policy_areas = self._subjects.member_subject_items(bioguide_id)
        model_version, _ = self.latest_model_version()
        if not model_version:
            return MemberTopicsResponse(
                bioguide_id=bioguide_id, subjects=subjects, policy_areas=policy_areas
            )
        bill_dates = self._member_bill_dates(bioguide_id)
        pairs = (
            self.member_assignments(list(bill_dates), model_version)
            if bill_dates
            else []
        )
        if not pairs:
            return MemberTopicsResponse(
                bioguide_id=bioguide_id,
                model_version=model_version,
                subjects=subjects,
                policy_areas=policy_areas,
            )
        summaries = self.topic_summaries(model_version)

        def label_of(topic_id: int) -> str:
            return (
                summaries[topic_id].label
                if topic_id in summaries
                else f"Topic {topic_id}"
            )

        totals: Counter[int] = Counter(topic_id for _, topic_id in pairs)
        total_count = sum(totals.values())
        topics = [
            TopicItem(label=label_of(topic_id), weight=round(count / total_count, 4))
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
                label=label_of(topic_id),
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

    def _search(self, body: dict[str, Any]) -> dict[str, Any] | None:
        try:
            return self._client.search(index=self._index, body=body)
        except NotFoundError:
            return None

    @staticmethod
    def _hits(response: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not response:
            return []
        return response.get("hits", {}).get("hits", [])

    def _metasubject_summaries(self, model_version: str) -> dict[int, MetasubjectSummary]:
        response = self._search({
            "size": _METASUBJECT_LIMIT,
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"kind": _METASUBJECT_KIND}},
                        {"term": {"model_version": model_version}},
                    ]
                }
            },
            "_source": ["metasubject_id", "name", "size", "top_words", "topic_ids"],
        })
        summaries = [
            MetasubjectSummary.model_validate(hit.get("_source", {}))
            for hit in self._hits(response)
        ]
        summaries.sort(key=lambda group: group.size, reverse=True)
        return {group.metasubject_id: group for group in summaries}

    def _metasubject_points(
        self, model_version: str, metasubject_ids: list[int] | None = None
    ) -> dict[int, list[TopicTrendPoint]]:
        filters: list[dict[str, Any]] = [
            {"term": {"kind": _METASUBJECT_TREND_KIND}},
            {"term": {"model_version": model_version}},
        ]
        if metasubject_ids is not None:
            filters.append({"terms": {"metasubject_id": metasubject_ids}})
        response = self._search({
            "size": _METASUBJECT_TREND_LIMIT,
            "query": {"bool": {"filter": filters}},
            "sort": [{"timestamp": {"order": "asc"}}],
        })
        points: dict[int, list[TopicTrendPoint]] = defaultdict(list)
        for hit in self._hits(response):
            source = hit.get("_source", {})
            points[int(source["metasubject_id"])].append(
                TopicTrendPoint(
                    timestamp=str(source.get("timestamp") or ""),
                    frequency=int(source.get("frequency") or 0),
                )
            )
        return points

    def _bill_titles(self, bill_ids: list[str]) -> dict[str, str]:
        if not bill_ids:
            return {}
        try:
            response = self._client.mget(
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

    def _member_bill_dates(self, bioguide_id: str) -> dict[str, str | None]:
        """Bill id → introduced date for bills the member sponsored/cosponsored."""
        try:
            response = self._client.search(
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
                                            {"term": {"cosponsor_bioguide_ids": bioguide_id}},
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

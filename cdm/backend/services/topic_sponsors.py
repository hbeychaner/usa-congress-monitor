"""Sponsor counts for the bills in one topic, metasubject or CRS subject."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from enum import StrEnum

from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch.helpers import scan
from pydantic import BaseModel

from cdm.backend.services.member_subject_overlay import SUBJECT_FIELD, SUBJECTS_PATH
from cdm.backend.services.sponsored_bills import SPONSOR_FIELD
from cdm.store.opensearch import read_alias

ID_CHUNK = 1024
SPONSOR_BUCKETS = 600


class CenterKind(StrEnum):
    TOPIC = "topic"
    METASUBJECT = "metasubject"
    SUBJECT = "subject"


class AssignmentField(StrEnum):
    TOPIC = "topic_id"
    METASUBJECT = "metasubject_id"


class SponsorBucket(BaseModel):
    key: str
    doc_count: int


class SponsorAggregation(BaseModel):
    buckets: list[SponsorBucket] = []


class SponsorAggregations(BaseModel):
    sponsors: SponsorAggregation = SponsorAggregation()


class SponsorResponse(BaseModel):
    aggregations: SponsorAggregations = SponsorAggregations()


class AssignedBillReader:
    """Bill ids assigned to a topic or metasubject by the latest trained model."""

    def __init__(self, client: Elasticsearch, analysis_index: str) -> None:
        self.client = client
        self.index = analysis_index

    def read(self, field: AssignmentField, value: int, model_version: str) -> list[str]:
        query = {
            "bool": {
                "filter": [
                    {"term": {"kind": "assignment"}},
                    {"term": {"model_version": model_version}},
                    {"term": {field.value: value}},
                ]
            }
        }
        try:
            return [
                str(hit["_source"]["doc_id"])
                for hit in scan(
                    self.client,
                    index=self.index,
                    query={"query": query, "_source": ["doc_id"]},
                )
                if hit["_source"].get("doc_id")
            ]
        except NotFoundError:
            return []


class TopicSponsorReader:
    def __init__(self, client: Elasticsearch) -> None:
        self.client = client

    def _count(self, query: dict[str, object]) -> Counter[str]:
        try:
            response = self.client.search(
                index=read_alias("bill"),
                body={
                    "size": 0,
                    "query": query,
                    "aggs": {"sponsors": {"terms": {"field": SPONSOR_FIELD, "size": SPONSOR_BUCKETS}}},
                },
            )
        except NotFoundError:
            return Counter()
        parsed = SponsorResponse.model_validate(response.body)
        return Counter({bucket.key: bucket.doc_count for bucket in parsed.aggregations.sponsors.buckets})

    @staticmethod
    def _filters(congress: int | None) -> list[dict[str, object]]:
        filters: list[dict[str, object]] = [{"term": {"source_type": "bill"}}]
        if congress:
            filters.append({"term": {"congress": congress}})
        return filters

    def by_bill_ids(self, bill_ids: Iterable[str], congress: int | None) -> Counter[str]:
        ids = list(bill_ids)
        totals: Counter[str] = Counter()
        for start in range(0, len(ids), ID_CHUNK):
            filters = self._filters(congress)
            filters.append({"ids": {"values": ids[start : start + ID_CHUNK]}})
            totals.update(self._count({"bool": {"filter": filters}}))
        return totals

    def by_subject(self, subject: str, congress: int | None) -> Counter[str]:
        filters = self._filters(congress)
        filters.append({
            "nested": {
                "path": SUBJECTS_PATH,
                "query": {"term": {SUBJECT_FIELD: subject}},
            }
        })
        return self._count({"bool": {"filter": filters}})

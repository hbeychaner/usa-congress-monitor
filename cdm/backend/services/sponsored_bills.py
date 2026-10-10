"""Sponsored bill ids per member, shared by the graph overlay builders."""

from __future__ import annotations

from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch.helpers import scan

from cdm.store.opensearch import read_alias

SPONSOR_FIELD = "sponsor_bioguide_ids"


class SponsoredBillReader:
    def __init__(self, client: Elasticsearch) -> None:
        self.client = client

    def by_member(self, member_ids: list[str], congress: int | None) -> dict[str, list[str]]:
        filters: list[dict[str, object]] = [
            {"term": {"source_type": "bill"}},
            {"terms": {SPONSOR_FIELD: member_ids}},
        ]
        if congress:
            filters.append({"term": {"congress": congress}})
        bills: dict[str, list[str]] = {}
        try:
            for hit in scan(
                self.client,
                index=read_alias("bill"),
                query={"query": {"bool": {"filter": filters}}, "_source": [SPONSOR_FIELD]},
            ):
                for sponsor in hit["_source"].get(SPONSOR_FIELD) or []:
                    if sponsor in member_ids:
                        bills.setdefault(sponsor, []).append(hit["_id"])
        except NotFoundError:
            return {}
        return bills

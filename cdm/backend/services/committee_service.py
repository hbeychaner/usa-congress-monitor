"""Bills referred to a committee or subcommittee, from the bills' own committee entries."""

from __future__ import annotations

from typing import Any

from elasticsearch import Elasticsearch

from cdm.contracts.api import CommitteeActivity, CommitteeBill, CommitteeDetailResponse
from cdm.store.opensearch import read_alias

_NESTED_PATH = "committees"
_CODE_FIELDS = ("committees.system_code", "committees.subcommittees.system_code")
_SOURCE_FIELDS = ["id", "title", "congress", "origin_chamber", "committees"]


class CommitteeService:
    def __init__(self, client: Elasticsearch) -> None:
        self.client = client

    def detail(
        self, system_code: str, page: int, limit: int
    ) -> CommitteeDetailResponse:
        response = self.client.search(
            index=read_alias("bill"),
            body={
                "from": (page - 1) * limit,
                "size": limit,
                "track_total_hits": True,
                "_source": _SOURCE_FIELDS,
                "query": {
                    "nested": {
                        "path": _NESTED_PATH,
                        "query": {
                            "bool": {
                                "should": [
                                    {"term": {field: system_code}}
                                    for field in _CODE_FIELDS
                                ],
                                "minimum_should_match": 1,
                            }
                        },
                    }
                },
                "sort": [{"update_date": {"order": "desc", "missing": "_last"}}],
            },
        )
        hits = response["hits"]
        name = system_code
        chamber: str | None = None
        committee_type: str | None = None
        bills: list[CommitteeBill] = []
        for hit in hits["hits"]:
            source: dict[str, Any] = hit["_source"]
            entry = self._entry(source.get("committees") or [], system_code)
            if entry is None:
                continue
            if name == system_code:
                name = str(entry.get("name") or system_code)
                chamber = entry.get("chamber")
                committee_type = entry.get("type")
            bills.append(
                CommitteeBill(
                    bill_id=str(source.get("id") or hit["_id"]),
                    title=str(source.get("title") or hit["_id"]),
                    congress=source.get("congress"),
                    chamber=source.get("origin_chamber"),
                    activities=[
                        CommitteeActivity(
                            name=str(a.get("name", "")), date=a.get("date")
                        )
                        for a in entry.get("activities") or []
                    ],
                )
            )
        total = (
            hits["total"]["value"] if isinstance(hits["total"], dict) else hits["total"]
        )
        return CommitteeDetailResponse(
            system_code=system_code,
            name=name,
            chamber=chamber,
            committee_type=committee_type,
            total=int(total),
            page=page,
            limit=limit,
            bills=bills,
        )

    def _entry(
        self, committees: list[dict[str, Any]], system_code: str
    ) -> dict[str, Any] | None:
        for committee in committees:
            if committee.get("system_code") == system_code:
                return committee
            for sub in committee.get("subcommittees") or []:
                if sub.get("system_code") == system_code:
                    return {
                        "chamber": committee.get("chamber"),
                        "type": "Subcommittee",
                        **sub,
                    }
        return None

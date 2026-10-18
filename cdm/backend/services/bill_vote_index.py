"""Bill-to-vote lookups across the Voteview roll call and Congress.gov House vote indices."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict

from cdm.store.opensearch import read_alias

_BILL_ID_PREFIX = "bill"
_MAX_BILLS = 20000


class LegislationType(StrEnum):
    HR = "HR"
    S = "S"
    HJRES = "HJRES"
    SJRES = "SJRES"
    HCONRES = "HCONRES"
    SCONRES = "SCONRES"
    HRES = "HRES"
    SRES = "SRES"


class BillKey(BaseModel):
    """Parsed bill id such as bill:119:hr:138."""

    model_config = ConfigDict(frozen=True)

    congress: int
    legislation_type: LegislationType
    number: int

    @classmethod
    def parse(cls, bill_id: str) -> BillKey | None:
        parts = bill_id.strip().split(":")
        if len(parts) != 4 or parts[0] != _BILL_ID_PREFIX:
            return None
        _, congress, bill_type, number = parts
        if not (congress.isdigit() and number.isdigit()):
            return None
        try:
            legislation_type = LegislationType(bill_type.upper())
        except ValueError:
            return None
        return cls(
            congress=int(congress),
            legislation_type=legislation_type,
            number=int(number),
        )

    @property
    def bill_id(self) -> str:
        return (
            f"{_BILL_ID_PREFIX}:{self.congress}:"
            f"{self.legislation_type.lower()}:{self.number}"
        )

    def house_vote_filter(self) -> dict[str, Any]:
        return {
            "bool": {
                "filter": [
                    {"term": {"congress": self.congress}},
                    {"term": {"legislation_type": self.legislation_type.value}},
                    {"term": {"legislation_number": self.number}},
                ]
            }
        }


class BillVoteIndex:
    """Finds which bills have recorded votes and how many."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def bill_ids(self, congress: int | None = None) -> list[str]:
        """Return ids of bills with at least one vote in either source."""
        congress_filter: list[dict[str, Any]] = (
            [{"term": {"congress": congress}}] if congress is not None else []
        )
        rollcall = self._client.search(
            index=read_alias("rollcall"),
            size=0,
            query={
                "bool": {
                    "filter": [
                        *congress_filter,
                        {"exists": {"field": "legislation_id"}},
                    ]
                }
            },
            aggs={"bills": {"terms": {"field": "legislation_id", "size": _MAX_BILLS}}},
        )
        ids = {
            str(bucket["key"])
            for bucket in rollcall["aggregations"]["bills"]["buckets"]
        }
        house = self._client.search(
            index=read_alias("house_vote"),
            size=0,
            query={"bool": {"filter": congress_filter}},
            aggs={
                "bills": {
                    "multi_terms": {
                        "terms": [
                            {"field": "congress"},
                            {"field": "legislation_type"},
                            {"field": "legislation_number"},
                        ],
                        "size": _MAX_BILLS,
                    }
                }
            },
        )
        for bucket in house["aggregations"]["bills"]["buckets"]:
            congress_value, type_value, number = bucket["key"]
            key = BillKey.parse(
                f"{_BILL_ID_PREFIX}:{congress_value}:{str(type_value).lower()}:{number}"
            )
            if key is not None:
                ids.add(key.bill_id)
        return sorted(ids)

    def counts(self, bill_ids: list[str]) -> dict[str, int]:
        """Return the larger of the two sources' vote counts per bill id."""
        keys = [key for bill_id in bill_ids if (key := BillKey.parse(bill_id))]
        if not keys:
            return {}
        rollcall = self._client.search(
            index=read_alias("rollcall"),
            size=0,
            query={"terms": {"legislation_id": [key.bill_id for key in keys]}},
            aggs={"bills": {"terms": {"field": "legislation_id", "size": len(keys)}}},
        )
        counts = {
            str(bucket["key"]): int(bucket["doc_count"])
            for bucket in rollcall["aggregations"]["bills"]["buckets"]
        }
        house = self._client.search(
            index=read_alias("house_vote"),
            size=0,
            query={
                "bool": {
                    "should": [key.house_vote_filter() for key in keys],
                    "minimum_should_match": 1,
                }
            },
            aggs={
                "bills": {
                    "multi_terms": {
                        "terms": [
                            {"field": "congress"},
                            {"field": "legislation_type"},
                            {"field": "legislation_number"},
                        ],
                        "size": len(keys),
                    }
                }
            },
        )
        for bucket in house["aggregations"]["bills"]["buckets"]:
            congress_value, type_value, number = bucket["key"]
            key = BillKey.parse(
                f"{_BILL_ID_PREFIX}:{congress_value}:{str(type_value).lower()}:{number}"
            )
            if key is not None:
                counts[key.bill_id] = max(
                    counts.get(key.bill_id, 0), int(bucket["doc_count"])
                )
        return {bill_id: count for bill_id, count in counts.items() if count}

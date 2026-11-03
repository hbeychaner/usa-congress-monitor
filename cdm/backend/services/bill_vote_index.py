"""Bill-to-vote lookups across the Voteview roll call and Congress.gov House vote indices."""

from __future__ import annotations

from enum import StrEnum

from elasticsearch import Elasticsearch
from pydantic import BaseModel, ConfigDict, ValidationError

from cdm.config.query_reads import ActivityKind, QueryReadConfig
from cdm.contracts.queries import QueryReadError
from cdm.store.client import IncompleteSearchError, SearchCompletion
from cdm.store.opensearch import read_alias
from cdm.utils.json_types import JsonObject


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
        if len(parts) != 4 or parts[0] != ActivityKind.BILL:
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
            f"{ActivityKind.BILL}:{self.congress}:"
            f"{self.legislation_type.lower()}:{self.number}"
        )

    def house_vote_filter(self) -> JsonObject:
        return {
            "bool": {
                "filter": [
                    {"term": {"congress": self.congress}},
                    {"term": {"legislation_type": self.legislation_type.value}},
                    {"term": {"legislation_number": self.number}},
                ]
            }
        }


class VoteSource(StrEnum):
    ROLLCALL = "rollcall"
    HOUSE = "house_vote"


class VoteBucket(BaseModel):
    key: str | tuple[int, str, int | str]
    doc_count: int

    @property
    def bill_id(self) -> str | None:
        if isinstance(self.key, str):
            return self.key
        congress, bill_type, number = self.key
        key = BillKey.parse(
            f"{ActivityKind.BILL}:{congress}:{bill_type.lower()}:{number}"
        )
        return key.bill_id if key is not None else None


class VoteBuckets(BaseModel):
    buckets: list[VoteBucket]
    sum_other_doc_count: int
    doc_count_error_upper_bound: int = 0


class BillVoteIndex:
    """Finds which bills have recorded votes and how many."""

    def __init__(
        self, client: Elasticsearch, reads: QueryReadConfig | None = None
    ) -> None:
        self._client = client
        self._reads = reads or QueryReadConfig()

    def _buckets(
        self, source: VoteSource, query: JsonObject, size: int
    ) -> list[VoteBucket]:
        aggregation: JsonObject = (
            {"terms": {"field": "legislation_id", "size": size}}
            if source == VoteSource.ROLLCALL
            else {
                "multi_terms": {
                    "terms": [
                        {"field": field}
                        for field in (
                            "congress",
                            "legislation_type",
                            "legislation_number",
                        )
                    ],
                    "size": size,
                }
            }
        )
        response = self._client.search(
            index=read_alias(source),
            size=0,
            query=query,
            aggs={"bills": aggregation},
            allow_partial_search_results=False,
        )
        SearchCompletion.model_validate(response.body).require_complete()
        try:
            result = VoteBuckets.model_validate(response["aggregations"]["bills"])
        except (KeyError, ValidationError) as exc:
            raise IncompleteSearchError("Vote aggregation is incomplete") from exc
        if result.sum_other_doc_count:
            raise QueryReadError(
                "The voted-bill filter exceeds its supported scope; select a Congress or use a narrower scope.",
                "has_votes",
            )
        if result.doc_count_error_upper_bound:
            raise IncompleteSearchError("Vote aggregation counts are approximate")
        return result.buckets

    def bill_ids(self, congress: int | None = None) -> list[str]:
        """Return ids of bills with at least one vote in either source."""
        congress_filter: list[JsonObject] = (
            [{"term": {"congress": congress}}] if congress is not None else []
        )
        ids: set[str] = set()
        for source in VoteSource:
            filters = [*congress_filter]
            if source == VoteSource.ROLLCALL:
                filters.append({"exists": {"field": "legislation_id"}})
            ids.update(
                bill_id
                for bucket in self._buckets(
                    source,
                    {"bool": {"filter": filters}},
                    self._reads.vote_bucket_limit,
                )
                if (bill_id := bucket.bill_id) is not None
            )
        return sorted(ids)

    def counts(self, bill_ids: list[str]) -> dict[str, int]:
        """Return the larger of the two sources' vote counts per bill id."""
        keys = [key for bill_id in bill_ids if (key := BillKey.parse(bill_id))]
        if not keys:
            return {}
        self._reads.offset(1, len(keys))
        counts: dict[str, int] = {}
        for source in VoteSource:
            query: JsonObject = (
                {"terms": {"legislation_id": [key.bill_id for key in keys]}}
                if source == VoteSource.ROLLCALL
                else {
                    "bool": {
                        "should": [key.house_vote_filter() for key in keys],
                        "minimum_should_match": 1,
                    }
                }
            )
            for bucket in self._buckets(source, query, len(keys)):
                if (bill_id := bucket.bill_id) is not None:
                    counts[bill_id] = max(counts.get(bill_id, 0), bucket.doc_count)
        return {bill_id: count for bill_id, count in counts.items() if count}

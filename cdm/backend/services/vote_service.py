"""OpenSearch-backed roll-call vote services for bills."""

from __future__ import annotations

from typing import Any

from elasticsearch import Elasticsearch

from cdm.contracts.api import BillVotesResponse, VotePartyTotals, VoteSummary
from cdm.store.opensearch import read_alias

# Maps the lowercase bill-type segment used in bill ids (e.g. "bill:119:hr:138")
# to the legislation_type value stored on house_vote documents (e.g. "HR").
_BILL_TYPE_TO_LEGISLATION_TYPE = {
    "hr": "HR",
    "s": "S",
    "hjres": "HJRES",
    "sjres": "SJRES",
    "hconres": "HCONRES",
    "sconres": "SCONRES",
    "hres": "HRES",
    "sres": "SRES",
}


class VoteService:
    """Roll-call vote lookups for bills."""

    def __init__(self, client: Elasticsearch) -> None:
        self._client = client

    def for_bill(self, bill_id: str, limit: int = 100) -> BillVotesResponse:
        """Return recorded House votes referencing the given bill.

        House vote documents carry the parent bill's legislation_type and
        legislation_number even for amendment votes, so filtering on congress +
        legislation_type + legislation_number captures the full vote history.
        """
        parts = bill_id.strip().split(":")
        if len(parts) != 4 or parts[0] != "bill":
            return BillVotesResponse(bill_id=bill_id, votes=[], total=0)

        _, congress_str, bill_type, number_str = parts
        legislation_type = _BILL_TYPE_TO_LEGISLATION_TYPE.get(bill_type.lower())
        if (
            legislation_type is None
            or not congress_str.isdigit()
            or not number_str.isdigit()
        ):
            return BillVotesResponse(bill_id=bill_id, votes=[], total=0)

        query = {
            "bool": {
                "filter": [
                    {"term": {"congress": int(congress_str)}},
                    {"term": {"legislation_type": legislation_type}},
                    {"term": {"legislation_number": int(number_str)}},
                ]
            }
        }
        response = self._client.search(
            index=read_alias("house_vote"),
            body={
                "size": limit,
                "track_total_hits": True,
                "query": query,
                "sort": [{"start_date": {"order": "desc"}}],
            },
        )
        hits = response.get("hits", {})
        total = hits.get("total", 0)
        if isinstance(total, dict):
            total = total.get("value", 0)

        votes = [self._summary(hit) for hit in hits.get("hits", [])]
        return BillVotesResponse(bill_id=bill_id, votes=votes, total=int(total))

    @staticmethod
    def _summary(hit: dict[str, Any]) -> VoteSummary:
        source: dict[str, Any] = hit.get("_source", {})
        totals = source.get("vote_party_total") or {}
        return VoteSummary(
            vote_id=str(source.get("id") or hit.get("_id") or ""),
            congress=source.get("congress"),
            session_number=source.get("session_number"),
            roll_call_number=source.get("roll_call_number"),
            vote_type=source.get("vote_type"),
            result=source.get("result"),
            question=(source.get("vote_question") or {}).get("question"),
            date=source.get("start_date"),
            totals=VotePartyTotals(
                yea=totals.get("yea", 0),
                nay=totals.get("nay", 0),
                present=totals.get("present", 0),
                not_voting=totals.get("not_voting", 0),
            ),
            amendment_number=source.get("amendment_number"),
            url=source.get("url"),
        )


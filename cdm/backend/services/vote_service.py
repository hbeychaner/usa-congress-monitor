"""Roll-call vote services for bills, merging Voteview and Congress.gov House votes."""

from __future__ import annotations

from typing import Any

from elasticsearch import Elasticsearch

from cdm.backend.services.bill_vote_index import BillKey
from cdm.contracts.api import BillVotesResponse, VotePartyTotals, VoteSummary
from cdm.ingest.voteview import Chamber as VoteviewChamber
from cdm.models.people import Chamber
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
_ROLLCALL_FIELDS = [
    "id",
    "congress",
    "chamber",
    "session_number",
    "roll_number",
    "clerk_roll_number",
    "date",
    "question",
    "result",
    "yea_count",
    "nay_count",
    "present_ids",
    "not_voting_ids",
]

_DedupeKey = tuple[str, int | None, int | None, int | None]


class VoteService:
    """Roll-call vote lookups for bills."""

    def __init__(self, client: Elasticsearch) -> None:
        self._client = client

    def for_bill(self, bill_id: str, limit: int = 100) -> BillVotesResponse:
        """Return House and Senate votes on a bill, de-duplicated across sources."""
        key = BillKey.parse(bill_id)
        if key is None:
            return BillVotesResponse(bill_id=bill_id, votes=[], total=0)

        merged: dict[_DedupeKey, VoteSummary] = {}
        for vote in self._rollcall_votes(key, limit):
            merged[self._dedupe_key(vote)] = vote
        # Congress.gov House records carry URLs and vote types, so they win ties.
        for vote in self._house_votes(key, limit):
            merged[self._dedupe_key(vote)] = vote

        votes = sorted(merged.values(), key=lambda vote: vote.date or "", reverse=True)
        return BillVotesResponse(bill_id=bill_id, votes=votes[:limit], total=len(votes))

    @staticmethod
    def _dedupe_key(vote: VoteSummary) -> _DedupeKey:
        return (vote.chamber, vote.congress, vote.session_number, vote.roll_call_number)

    def _rollcall_votes(self, key: BillKey, limit: int) -> list[VoteSummary]:
        response = self._client.search(
            index=read_alias("rollcall"),
            size=limit,
            query={"term": {"legislation_id": key.bill_id}},
            sort=[{"date": {"order": "desc"}}],
            source_includes=_ROLLCALL_FIELDS,
        )
        return [self._rollcall_summary(hit) for hit in response["hits"]["hits"]]

    def _house_votes(self, key: BillKey, limit: int) -> list[VoteSummary]:
        response = self._client.search(
            index=read_alias("house_vote"),
            size=limit,
            query=key.house_vote_filter(),
            sort=[{"start_date": {"order": "desc"}}],
        )
        return [self._house_summary(hit) for hit in response["hits"]["hits"]]

    @staticmethod
    def _rollcall_summary(hit: dict[str, Any]) -> VoteSummary:
        source: dict[str, Any] = hit.get("_source", {})
        is_house = source.get("chamber") == VoteviewChamber.HOUSE
        # Voteview House roll numbers differ from the Clerk's; match on the Clerk number.
        roll_number = (
            source.get("clerk_roll_number") if is_house else source.get("roll_number")
        )
        return VoteSummary(
            vote_id=str(source.get("id") or hit.get("_id") or ""),
            congress=source.get("congress"),
            session_number=source.get("session_number"),
            roll_call_number=roll_number,
            chamber=Chamber.HOUSE if is_house else Chamber.SENATE,
            result=source.get("result"),
            question=source.get("question"),
            date=source.get("date"),
            totals=VotePartyTotals(
                yea=source.get("yea_count") or 0,
                nay=source.get("nay_count") or 0,
                present=len(source.get("present_ids") or []),
                not_voting=len(source.get("not_voting_ids") or []),
            ),
        )

    @staticmethod
    def _house_summary(hit: dict[str, Any]) -> VoteSummary:
        source: dict[str, Any] = hit.get("_source", {})
        totals = source.get("vote_party_total") or {}
        return VoteSummary(
            vote_id=str(source.get("id") or hit.get("_id") or ""),
            congress=source.get("congress"),
            session_number=source.get("session_number"),
            roll_call_number=source.get("roll_call_number"),
            chamber=Chamber.HOUSE,
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

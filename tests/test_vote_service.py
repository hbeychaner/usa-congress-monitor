from typing import Any
from unittest.mock import MagicMock

from elasticsearch import Elasticsearch

from cdm.backend.services.bill_vote_index import BillKey, BillVoteIndex
from cdm.backend.services.vote_service import VoteService
from cdm.store.opensearch import read_alias

BILL_ID = "bill:119:hr:1"


def _hits(sources: list[dict[str, Any]]) -> dict[str, Any]:
    return {"hits": {"hits": [{"_source": source} for source in sources]}}


def _client(rollcall: list[dict[str, Any]], house: list[dict[str, Any]]) -> MagicMock:
    client = MagicMock(spec=Elasticsearch)

    def search(index: str, **_: Any) -> dict[str, Any]:
        return _hits(rollcall if index == read_alias("rollcall") else house)

    client.search.side_effect = search
    return client


def _rollcall(
    chamber: str, roll: int, clerk: int, date: str, session: int = 1
) -> dict[str, Any]:
    return {
        "id": f"rollcall:119:{chamber}:{roll}",
        "congress": 119,
        "chamber": chamber,
        "session_number": session,
        "roll_number": roll,
        "clerk_roll_number": clerk,
        "date": date,
        "question": "On Passage",
        "result": "Passed",
        "yea_count": 215,
        "nay_count": 214,
        "present_ids": ["a"],
        "not_voting_ids": ["b", "c"],
    }


def test_bill_key_parses_and_rejects() -> None:
    key = BillKey.parse(BILL_ID)
    assert key is not None
    assert key.bill_id == BILL_ID
    assert BillKey.parse("bill:119:xx:1") is None
    assert BillKey.parse("member:A000001") is None


def test_unknown_bill_id_returns_no_votes() -> None:
    response = VoteService(_client([], [])).for_bill("nonsense")
    assert response.votes == []
    assert response.total == 0


def test_merges_both_chambers_and_prefers_house_vote_record() -> None:
    rollcall = [
        _rollcall("house", 144, 145, "2025-05-22"),
        _rollcall("senate", 329, 329, "2025-06-28"),
    ]
    house = [
        {
            "id": "house-rollcall-vote:119:1:145",
            "congress": 119,
            "session_number": 1,
            "roll_call_number": 145,
            "start_date": "2025-05-22",
            "vote_type": "Yea-and-Nay",
            "url": "https://example.test/145",
            "vote_party_total": {"yea": 215, "nay": 214},
        }
    ]
    response = VoteService(_client(rollcall, house)).for_bill(BILL_ID)

    assert response.total == 2
    assert [vote.chamber for vote in response.votes] == ["Senate", "House"]
    senate, house_vote = response.votes
    assert senate.totals.present == 1
    assert senate.totals.not_voting == 2
    assert house_vote.url == "https://example.test/145"


def test_has_votes_ids_union_both_sources() -> None:
    client = MagicMock(spec=Elasticsearch)

    def search(index: str, **_: Any) -> dict[str, Any]:
        if index == read_alias("rollcall"):
            buckets = [{"key": "bill:119:hr:1", "doc_count": 3}]
        else:
            buckets = [{"key": [118, "S", 7], "doc_count": 2}]
        return {"aggregations": {"bills": {"buckets": buckets}}}

    client.search.side_effect = search
    assert BillVoteIndex(client).bill_ids() == ["bill:118:s:7", "bill:119:hr:1"]


def test_counts_take_larger_source_and_skip_bills_without_votes() -> None:
    client = MagicMock(spec=Elasticsearch)

    def search(index: str, **_: Any) -> dict[str, Any]:
        if index == read_alias("rollcall"):
            buckets = [{"key": BILL_ID, "doc_count": 3}]
        else:
            buckets = [{"key": [119, "HR", 1], "doc_count": 5}]
        return {"aggregations": {"bills": {"buckets": buckets}}}

    client.search.side_effect = search
    counts = BillVoteIndex(client).counts([BILL_ID, "bill:119:s:9"])
    assert counts == {BILL_ID: 5}

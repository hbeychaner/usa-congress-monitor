from typing import Any
from unittest.mock import MagicMock

from elasticsearch import Elasticsearch, NotFoundError

from cdm.backend.services.vote_breakdown_service import VoteBreakdownService
from cdm.contracts.api import VotePosition
from cdm.graph.models import PartyGroup

ROLLCALL = {
    "yea_ids": ["R1", "R2", "D1"],
    "nay_ids": ["D2", "D3"],
    "present_ids": [],
    "not_voting_ids": ["I1", "X9"],
}


def _member(bioguide_id: str, party: str, name: str) -> dict[str, Any]:
    return {
        "_source": {
            "bioguide_id": bioguide_id,
            "party_name": party,
            "name": name,
            "state": "Ohio",
        }
    }


def _service() -> VoteBreakdownService:
    client = MagicMock(spec=Elasticsearch)
    client.get.return_value = {"_source": ROLLCALL}
    client.search.return_value = {
        "hits": {
            "hits": [
                _member("R1", "Republican", "Adams, A"),
                _member("R2", "Republican", "Baker, B"),
                _member("D1", "Democratic", "Clark, C"),
                _member("D2", "Democratic", "Davis, D"),
                _member("D3", "Democratic", "Evans, E"),
                _member("I1", "Independent", "Frank, F"),
            ]
        }
    }
    return VoteBreakdownService(client)


def _count(response: Any, party: PartyGroup, position: VotePosition) -> int:
    row = next(row for row in response.parties if row.party == party)
    return len(next(p for p in row.positions if p.position == position).members)


def test_groups_members_by_party_and_position() -> None:
    response = _service().for_vote("rollcall:119:house:1")
    assert response is not None
    assert [row.party for row in response.parties] == [
        PartyGroup.DEMOCRATIC,
        PartyGroup.REPUBLICAN,
        PartyGroup.OTHER,
    ]
    assert _count(response, PartyGroup.REPUBLICAN, VotePosition.YEA) == 2
    assert _count(response, PartyGroup.DEMOCRATIC, VotePosition.NAY) == 2
    assert _count(response, PartyGroup.DEMOCRATIC, VotePosition.YEA) == 1


def test_unmatched_members_fall_under_other() -> None:
    response = _service().for_vote("rollcall:119:house:1")
    assert response is not None
    assert _count(response, PartyGroup.OTHER, VotePosition.NOT_VOTING) == 2


def test_missing_rollcall_returns_none() -> None:
    client = MagicMock(spec=Elasticsearch)
    client.get.side_effect = NotFoundError("not found", MagicMock(), {})
    assert VoteBreakdownService(client).for_vote("rollcall:0:house:0") is None

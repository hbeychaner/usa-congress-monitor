"""Per-party breakdown of one roll call vote, with the members behind each position."""

from __future__ import annotations

from typing import Any

from elasticsearch import Elasticsearch, NotFoundError

from cdm.contracts.api import (
    PartyVoteBreakdown,
    PositionMembers,
    VoteBreakdownResponse,
    VoteMember,
    VotePosition,
)
from cdm.graph.models import PartyGroup
from cdm.store.opensearch import read_alias

_POSITION_FIELDS: dict[VotePosition, str] = {
    VotePosition.YEA: "yea_ids",
    VotePosition.NAY: "nay_ids",
    VotePosition.PRESENT: "present_ids",
    VotePosition.NOT_VOTING: "not_voting_ids",
}
_MEMBER_FIELDS = [
    "bioguide_id",
    "party",
    "party_name",
    "name",
    "full_name",
    "inverted_order_name",
    "state",
]
_PARTY_ORDER = [PartyGroup.DEMOCRATIC, PartyGroup.REPUBLICAN, PartyGroup.OTHER]


class VoteBreakdownService:
    """Groups a roll call's member positions by party."""

    def __init__(self, client: Elasticsearch) -> None:
        self._client = client

    def for_vote(self, vote_id: str) -> VoteBreakdownResponse | None:
        try:
            response = self._client.get(index=read_alias("rollcall"), id=vote_id)
        except NotFoundError:
            return None
        source: dict[str, Any] = response.get("_source", {})
        ids_by_position = {
            position: [str(item) for item in source.get(field) or []]
            for position, field in _POSITION_FIELDS.items()
        }
        members = self._members(
            [member_id for ids in ids_by_position.values() for member_id in ids]
        )

        grouped: dict[PartyGroup, dict[VotePosition, list[VoteMember]]] = {
            party: {position: [] for position in VotePosition} for party in _PARTY_ORDER
        }
        for position, ids in ids_by_position.items():
            for member_id in ids:
                party, member = members.get(
                    member_id,
                    (
                        PartyGroup.OTHER,
                        VoteMember(bioguide_id=member_id, name=member_id),
                    ),
                )
                grouped[party][position].append(member)

        parties = [
            PartyVoteBreakdown(
                party=party,
                positions=[
                    PositionMembers(
                        position=position,
                        members=sorted(grouped[party][position], key=lambda m: m.name),
                    )
                    for position in VotePosition
                ],
            )
            for party in _PARTY_ORDER
            if any(grouped[party].values())
        ]
        return VoteBreakdownResponse(vote_id=vote_id, parties=parties)

    def _members(self, ids: list[str]) -> dict[str, tuple[PartyGroup, VoteMember]]:
        if not ids:
            return {}
        response = self._client.search(
            index=read_alias("member"),
            size=len(ids),
            query={"terms": {"bioguide_id": ids}},
            source_includes=_MEMBER_FIELDS,
        )
        found: dict[str, tuple[PartyGroup, VoteMember]] = {}
        for hit in response["hits"]["hits"]:
            source: dict[str, Any] = hit["_source"]
            bioguide_id = str(source["bioguide_id"])
            name = str(
                source.get("inverted_order_name")
                or source.get("name")
                or source.get("full_name")
                or bioguide_id
            )
            party = PartyGroup.of(
                str(source.get("party_name") or source.get("party") or "")
            )
            found[bioguide_id] = (
                party,
                VoteMember(
                    bioguide_id=bioguide_id, name=name, state=source.get("state")
                ),
            )
        return found

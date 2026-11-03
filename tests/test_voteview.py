from pathlib import Path

import pytest
from pydantic import ValidationError

from cdm.ingest.voteview import (
    Chamber,
    MemberRow,
    RollCallBuilder,
    RollCallDocument,
    VoteRow,
)


def _write(path: Path, header: str, rows: list[str]) -> None:
    path.write_text("\n".join([header, *rows]) + "\n")


def _roll_call(bill_number: str | None) -> RollCallDocument:
    return RollCallDocument(
        congress=113, chamber=Chamber.HOUSE, roll_number=1, bill_number=bill_number
    )


def test_legislation_id() -> None:
    assert _roll_call("HRES5").legislation_id == "bill:113:hres:5"
    assert _roll_call("Boehner").legislation_id is None


def test_rollcall_party_split_and_defectors(tmp_path: Path) -> None:
    members = tmp_path / "m.csv"
    rollcalls = tmp_path / "r.csv"
    votes = tmp_path / "v.csv"
    _write(
        members,
        "chamber,icpsr,party_code,bioguide_id",
        [
            "House,1,100,D1",
            "House,2,100,D2",
            "House,3,100,D3",
            "House,4,200,R1",
            "House,5,200,R2",
            "House,6,200,R3",
            "President,9,100,P1",
        ],
    )
    _write(
        rollcalls,
        "congress,chamber,rollnumber,date,session,clerk_rollnumber,bill_number,"
        "vote_result,vote_desc,vote_question,dtl_desc",
        ["113,House,1,2013-01-03,1,2,HR7,Passed,desc,On Passage,"],
    )
    _write(
        votes,
        "congress,chamber,rollnumber,icpsr,cast_code,prob",
        [
            "113,House,1,1,1,100",
            "113,House,1,2,1,100",
            "113,House,1,3,6,100",
            "113,House,1,4,6,100",
            "113,House,1,5,6,100",
            "113,House,1,6,9,100",
        ],
    )
    (roll_call,) = RollCallBuilder(members, rollcalls, votes).build()
    doc = roll_call.to_index_document()
    assert doc["id"] == "rollcall:113:house:1"
    assert doc["legislation_id"] == "bill:113:hr:7"
    assert doc["party_split"] is True
    assert doc["defector_ids"] == ["D3"]
    assert doc["not_voting_ids"] == ["R3"]


@pytest.mark.parametrize("identity", ["10713", "10713.0", "10713.000"])
def test_icpsr_identity_joins_integral_csv_representations(identity: str) -> None:
    member = MemberRow.model_validate(
        {"chamber": "house", "icpsr": "10713", "bioguide_id": "A"}
    )
    vote = VoteRow.model_validate({"rollnumber": 1, "icpsr": identity, "cast_code": 1})
    assert member.icpsr == vote.icpsr == 10713


@pytest.mark.parametrize("identity", ["10713.5", "NaN", "inf", "", "0", "-1"])
def test_invalid_icpsr_identity_is_rejected(identity: str) -> None:
    with pytest.raises(ValidationError):
        VoteRow.model_validate({"rollnumber": 1, "icpsr": identity, "cast_code": 1})


@pytest.mark.parametrize("identity", ["1.0", "2"])
def test_builder_links_numeric_ids_or_fails_before_emitting(
    tmp_path: Path, identity: str
) -> None:
    members, rolls, votes = (tmp_path / name for name in ("m.csv", "r.csv", "v.csv"))
    _write(members, "chamber,icpsr,bioguide_id", ["House,1,A"])
    _write(rolls, "congress,chamber,rollnumber", ["114,House,1"])
    _write(votes, "rollnumber,icpsr,cast_code", [f"1,{identity},1"])
    builder = RollCallBuilder(members, rolls, votes)
    if identity == "2":
        with pytest.raises(ValueError, match="unlinked ICPSR"):
            next(builder.build())
    else:
        assert next(builder.build()).yea_ids == ["A"]


@pytest.mark.parametrize(
    "failure", ["missing_id", "conflict", "missing_roll", "orphan_roll", "empty_votes"]
)
def test_invalid_linkage_fails_before_any_replacement(
    tmp_path: Path, failure: str
) -> None:
    members, rolls, votes = (tmp_path / name for name in ("m.csv", "r.csv", "v.csv"))
    member_rows = ["House,1,A"]
    if failure == "missing_id":
        member_rows = ["House,1,"]
    elif failure == "conflict":
        member_rows.append("House,1,B")
    _write(members, "chamber,icpsr,bioguide_id", member_rows)
    _write(
        rolls,
        "congress,chamber,rollnumber",
        ["114,House,1", "114,House,2"]
        if failure == "missing_roll"
        else ["114,House,1"],
    )
    _write(
        votes,
        "rollnumber,icpsr,cast_code",
        []
        if failure == "empty_votes"
        else [f"{2 if failure == 'orphan_roll' else 1},1.0,1"],
    )
    with pytest.raises(ValueError):
        next(RollCallBuilder(members, rolls, votes).build())


def test_president_vote_is_explicitly_excluded(tmp_path: Path) -> None:
    members, rolls, votes = (tmp_path / name for name in ("m.csv", "r.csv", "v.csv"))
    _write(members, "chamber,icpsr,bioguide_id", ["House,1,A", "President,9,"])
    _write(rolls, "congress,chamber,rollnumber", ["114,House,1"])
    _write(votes, "rollnumber,icpsr,cast_code", ["1,1.0,1", "1,9.0,1"])
    assert next(RollCallBuilder(members, rolls, votes).build()).yea_ids == ["A"]

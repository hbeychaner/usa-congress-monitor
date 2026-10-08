from cdm.ingest.voteview import Chamber, RollCallBuilder, RollCallDocument


def _write(path, header, rows):
    path.write_text("\n".join([header, *rows]) + "\n")


def _roll_call(bill_number):
    return RollCallDocument(
        congress=113, chamber=Chamber.HOUSE, roll_number=1, bill_number=bill_number
    )


def test_legislation_id():
    assert _roll_call("HRES5").legislation_id == "bill:113:hres:5"
    assert _roll_call("Boehner").legislation_id is None


def test_rollcall_party_split_and_defectors(tmp_path):
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

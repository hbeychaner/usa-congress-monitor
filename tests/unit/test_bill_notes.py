import datetime

from src.models.bills import Bill


def test_bill_accepts_list_shaped_notes():
    data = {
        "congress": 110,
        "latestAction": {"text": "Referred to the Subcommittee."},
        "laws": [],
        "number": "29",
        "originChamber": "House",
        "originChamberCode": "H",
        "title": "Test title",
        "type": "HCONRES",
        "updateDate": "2025-06-06T14:17:56Z",
        "updateDateIncludingText": "2025-06-06T14:18:51Z",
        "notes": [{"text": "For further action, see S.2739."}],
    }

    inst = Bill.model_validate(data)
    assert inst is not None
    assert getattr(inst, "notes", None) is not None
    # notes should be a list with Note objects
    notes = inst.notes
    assert isinstance(notes, list)
    assert len(notes) == 1
    assert getattr(notes[0], "text", None) == "For further action, see S.2739."

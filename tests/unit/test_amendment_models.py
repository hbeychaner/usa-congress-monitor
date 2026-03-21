from datetime import datetime

from src.models.other_models import AmendmentListItem
from src.models.bills import Amendment


def test_amendment_list_item_parse():
    sample = {
        "congress": 117,
        "description": "An amendment to ...",
        "latestAction": {"actionDate": "2021-03-03T00:00:00Z", "text": "Submitted"},
        "number": "A1",
        "purpose": "Clarify language",
        "type": "HAMDT",
        "updateDate": "2021-03-03T00:00:00Z",
        "url": "https://api.congress.gov/v3/amendment/117/hamdt/1",
    }

    inst = AmendmentListItem.model_validate(sample)
    assert inst.congress == 117
    assert inst.number == "A1"
    assert inst.type == "HAMDT"
    assert inst.url.host == "api.congress.gov"


def test_amendment_model_parse():
    sample = {
        "congress": 116,
        "number": "1",
        "type": "SAMDT",
        "updateDate": "2020-06-01T00:00:00Z",
        "url": "https://api.congress.gov/v3/amendment/116/samdt/1",
    }

    a = Amendment.model_validate(sample)
    assert a.congress == 116
    assert a.number == "1"
    assert a.type == "SAMDT"
    # update_date should be parsed
    assert isinstance(a.update_date, datetime)

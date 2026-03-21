from src.models.other_models import LawListItem


def test_law_list_item_parse():
    sample = {
        "congress": 117,
        "laws": [{"number": "34", "type": "Public Law"}],
        "number": "123",
        "title": "An Act",
        "type": "HR",
        "updateDate": "2021-04-01T00:00:00Z",
        "url": "https://api.congress.gov/v3/law/117/pub/34",
    }

    inst = LawListItem.model_validate(sample)
    assert inst.congress == 117
    assert inst.laws and inst.laws[0].number == "34"
    assert inst.url.host == "api.congress.gov"

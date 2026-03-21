from datetime import datetime

import pytest

from src.models.bills import BillTextResponse, BillActionsResponse


def test_bill_text_response_parse():
    sample = {
        "pagination": None,
        "request": {"format": "json"},
        "textVersions": [
            {
                "date": "2020-01-01T00:00:00Z",
                "formats": [
                    {"type": "Formatted Text", "url": "https://example.com/text/1"}
                ],
                "type": "Asintroduced",
            }
        ],
    }

    resp = BillTextResponse.model_validate(sample)
    assert resp.textVersions
    tv = resp.textVersions[0]
    assert tv.type == "Asintroduced"
    assert any(f.url.host for f in tv.formats)
    # ensure date parsed
    assert isinstance(tv.date, datetime)


def test_bill_actions_response_parse():
    sample = {
        "pagination": None,
        "request": {},
        "actions": [
            {
                "actionDate": "2021-05-05T12:34:56Z",
                "text": "Introduced in House",
                "actionCode": "00",
            }
        ],
    }

    resp = BillActionsResponse.model_validate(sample)
    assert resp.actions
    a = resp.actions[0]
    assert a.text == "Introduced in House"
    assert a.action_code == "00"
    assert isinstance(a.action_date, datetime)

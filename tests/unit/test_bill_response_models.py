from datetime import UTC, datetime

from cdm.models.bills import (
    BillActionsResponse,
    BillMetadata,
    BillTextResponse,
    RelationshipDetail,
    Subjects,
)


def test_bill_metadata_preserves_fractional_source_number():
    bill = BillMetadata.model_validate({
        "congress": 117,
        "number": "260½",
        "title": "Historical bill",
        "type": "hr",
        "url": "https://api.congress.gov/v3/bill/117/hr/260%C2%BD",
    })

    assert bill.number == "260½"
    assert bill.id == "bill:117:hr:260½"


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


def test_bill_text_response_allows_null_text_version_date():
    resp = BillTextResponse.model_validate({
        "textVersions": [{"date": None, "formats": [], "type": "Introduced"}],
    })

    assert resp.textVersions[0].date is None


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


def test_bill_action_accepts_time_only_historical_action_time():
    resp = BillActionsResponse.model_validate({
        "actions": [{
            "actionDate": "2005-02-01T00:00:00Z",
            "actionTime": "18:55:59",
            "text": "Introduced in House",
        }]
    })

    assert resp.actions[0].action_time == datetime(2005, 2, 1, 18, 55, 59, tzinfo=UTC)


def test_bill_action_accepts_minimal_historical_committee_metadata():
    resp = BillActionsResponse.model_validate({
        "actions": [
            {
                "text": "Referred to committee",
                "committees": [{"name": "Financial Services"}],
            }
        ]
    })

    assert resp.actions[0].committees is not None
    assert resp.actions[0].committees[0].name == "Financial Services"


def test_bill_response_accepts_missing_policy_area():
    subjects = Subjects.model_validate({"legislativeSubjects": []})

    assert subjects.policy_area is None


def test_relationship_detail_accepts_library_of_congress():
    relationship = RelationshipDetail.model_validate(
        {"identifiedBy": "Library of Congress", "type": "related"}
    )

    assert relationship.identified_by.value == "Library of Congress"

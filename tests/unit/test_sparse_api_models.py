from cdm.models.bills import Action, IdentifyingEntity, RelationshipDetail
from cdm.models.people import Sponsor


def _sponsor_payload(**overrides: object) -> dict[str, object]:
    return {
        "bioguideId": "A000001",
        "firstName": "Ada",
        "lastName": "Example",
        "fullName": "Example, Ada",
        **overrides,
    }


def test_sponsor_accepts_blank_dates_and_null_state() -> None:
    sponsor = Sponsor.model_validate(
        _sponsor_payload(sponsorshipDate="", sponsorshipWithdrawnDate="", state=None)
    )

    assert sponsor.sponsorship_date is None
    assert sponsor.sponsorship_withrawn_date is None
    assert sponsor.state == ""


def test_sponsor_accepts_missing_state() -> None:
    assert Sponsor.model_validate(_sponsor_payload()).state == ""


def test_sponsor_keeps_real_values() -> None:
    sponsor = Sponsor.model_validate(
        _sponsor_payload(sponsorshipDate="2019-01-03", state="TX")
    )

    assert sponsor.sponsorship_date is not None
    assert sponsor.state == "TX"


def test_action_accepts_vote_without_url_and_missing_text() -> None:
    action = Action.model_validate(
        {
            "actionDate": "1977-03-01",
            "recordedVotes": [
                {
                    "chamber": "House",
                    "congress": 95,
                    "date": "1977-03-01T00:00:00Z",
                    "rollNumber": 9,
                    "sessionNumber": 1,
                }
            ],
        }
    )

    assert action.text == ""
    assert action.recorded_votes[0].url is None


def test_relationship_identified_by_government_publishing_office() -> None:
    detail = RelationshipDetail.model_validate(
        {"identifiedBy": "U.S. Government Publishing Office", "type": "Related bill"}
    )

    assert detail.identified_by is IdentifyingEntity.GOVERNMENT_PUBLISHING_OFFICE

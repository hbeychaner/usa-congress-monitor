from src.models import meta_models


def test_committee_meetings_response_parsing():
    raw = {"committeeMeetings": [{"eventId": 1}], "pagination": {"count": 1}}
    parsed = meta_models.CommitteeMeetingsResponse.model_validate(raw)
    assert isinstance(parsed.committeeMeetings, list)
    assert parsed.pagination["count"] == 1


def test_hearings_response_parsing():
    raw = {"hearings": [{"jacketNumber": 10}], "pagination": {"count": 1}}
    parsed = meta_models.HearingsResponse.model_validate(raw)
    assert isinstance(parsed.hearings, list)
    assert parsed.pagination["count"] == 1


def test_amendments_response_parsing():
    raw = {"amendments": [{"number": "A1"}], "pagination": {"count": 1}}
    parsed = meta_models.AmendmentsResponse.model_validate(raw)
    assert isinstance(parsed.amendments, list)
    assert parsed.pagination["count"] == 1

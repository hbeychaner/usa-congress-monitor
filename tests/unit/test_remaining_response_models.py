from src.models import meta_models


def test_congress_response_parsing():
    raw = {"congresses": [{"number": 118}], "pagination": {"count": 1}}
    parsed = meta_models.CongressListResponse.model_validate(raw)
    assert isinstance(parsed.congresses, list)


def test_committee_list_response_parsing():
    raw = {"committees": [{"name": "Budget"}], "pagination": {"count": 1}}
    parsed = meta_models.CommitteeListResponse.model_validate(raw)
    assert isinstance(parsed.committees, list)


def test_nomination_list_response_parsing():
    raw = {
        "nominations": [{"id": "N1", "congress": 118, "number": 1}],
        "pagination": {"count": 1},
    }
    parsed = meta_models.NominationListResponse.model_validate(raw)
    assert isinstance(parsed.nominations, list)


def test_bound_and_daily_responses():
    raw1 = {"boundCongressionalRecord": [{"year": 1990}], "pagination": {"count": 1}}
    raw2 = {"dailyCongressionalRecord": [{"id": 1}], "pagination": {"count": 1}}
    assert meta_models.BoundCongressionalRecordResponse.model_validate(raw1)
    assert meta_models.DailyCongressionalRecordResponse.model_validate(raw2)


def test_summaries_treaty_house_responses():
    raw = {
        "summaries": [{"bill": {"congress": 118, "type": "HR", "number": 1}}],
        "pagination": {"count": 1},
    }
    assert meta_models.SummariesResponse.model_validate(raw)
    raw2 = {"treaties": [{"id": "T1"}], "pagination": {"count": 1}}
    assert meta_models.TreatyListResponse.model_validate(raw2)
    raw3 = {
        "houseRequirements": [{"id": "HR1", "number": 1}],
        "pagination": {"count": 1},
    }
    assert meta_models.HouseRequirementsResponse.model_validate(raw3)


def test_house_votes_response():
    raw = {"houseRollCallVotes": [{"id": "V1"}], "pagination": {"count": 1}}
    assert meta_models.HouseVotesResponse.model_validate(raw)

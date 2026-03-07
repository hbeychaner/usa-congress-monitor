from src.models import meta_models


def test_bill_list_response_parsing():
    raw = {"bills": [{"number": "H123", "type": "HR"}], "pagination": {"count": 1}}
    parsed = meta_models.BillListResponse.model_validate(raw)
    assert isinstance(parsed.bills, list)
    assert parsed.pagination is not None
    assert parsed.pagination["count"] == 1


def test_member_list_response_parsing():
    raw = {"members": [{"bioguideId": "A000", "name": "Jane Doe"}], "pagination": {"count": 1}}
    parsed = meta_models.MemberListResponse.model_validate(raw)
    assert isinstance(parsed.members, list)
    assert parsed.pagination is not None
    assert parsed.pagination["count"] == 1


def test_crs_reports_response_parsing():
    raw = {"CRSReports": [{"id": "CRS1", "title": "Report"}], "pagination": {"count": 1}}
    parsed = meta_models.CRSReportsResponse.model_validate(raw)
    assert isinstance(parsed.CRSReports, list)
    assert parsed.pagination is not None
    assert parsed.pagination["count"] == 1

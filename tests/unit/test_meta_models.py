from src.models import meta_models


def test_bill_meta_parsing_and_dump():
    raw = {"congress": "118", "offset": "0", "limit": "50", "type": "HR"}
    m = meta_models.BillMeta.model_validate(raw)
    assert isinstance(m.offset, int)
    assert m.offset == 0
    assert isinstance(m.limit, int)
    assert m.limit == 50
    assert isinstance(m.congress, int)
    assert m.congress == 118
    assert m.type == "HR"
    dumped = m.model_dump(by_alias=True, exclude_none=True)
    assert dumped["offset"] == 0
    assert dumped["limit"] == 50
    assert dumped["congress"] == 118
    assert dumped["type"] == "HR"


def test_crsreport_meta_parsing_and_dump():
    raw = {"year": "2023", "offset": "10", "limit": "5"}
    m = meta_models.CRSReportMeta.model_validate(raw)
    assert m.year == 2023
    assert m.offset == 10
    assert m.limit == 5
    dumped = m.model_dump(by_alias=True, exclude_none=True)
    assert dumped["year"] == 2023
    assert dumped["offset"] == 10
    assert dumped["limit"] == 5

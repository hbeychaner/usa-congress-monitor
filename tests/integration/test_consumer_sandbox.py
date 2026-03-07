import pytest

from src.data_collection.queueing.specs import (
    SPECS,
    prepare_api_meta,
    resolve_pagination_for_consumer,
    fetch_page,
)


def test_sandbox_bill_flow(monkeypatch):
    # Patch the bills endpoint to return a deterministic response
    def fake_get_bills_metadata(client, offset, limit):
        return {
            "bills": [{"congress": 118, "type": "HR", "number": "H1"}],
            "pagination": {"count": 1},
        }

    monkeypatch.setattr(
        "src.data_collection.queueing.specs.get_bills_metadata",
        fake_get_bills_metadata,
    )

    spec = SPECS["bill"]
    raw_meta = {"congress": 118, "type": "HR", "offset": 0, "limit": 1}
    api_meta, meta_obj, filtered_meta = prepare_api_meta(spec, raw_meta)
    offset, limit = resolve_pagination_for_consumer(
        "bill", spec, raw_meta, meta_obj, filtered_meta
    )

    client = None
    resp = fetch_page("bill", client, offset=offset, limit=limit, meta=api_meta)
    # Parse via response_model if provided
    if spec.response_model is not None:
        parsed = spec.response_model.model_validate(resp)
        records = getattr(parsed, spec.api_data_key, []) or []
    else:
        records = resp.get(spec.api_data_key, [])
    assert len(records) == 1
    # id_func should succeed (convert Pydantic item to dict if needed)
    rec0 = records[0]
    if hasattr(rec0, "model_dump"):
        rec0 = rec0.model_dump()
    assert spec.id_func(rec0)


def test_sandbox_committee_report_flow(monkeypatch):
    # Patch the specific committee-report endpoint used when congress+reportType provided
    def fake_get_by_congress_and_type(client, congress, reportType, offset, limit):
        return {
            "reports": [{"congress": congress, "reportType": reportType, "id": "R1"}],
            "pagination": {"count": 1},
        }

    monkeypatch.setattr(
        "src.data_collection.queueing.specs.get_committee_reports_by_congress_and_type",
        fake_get_by_congress_and_type,
    )

    spec = SPECS["committee-report"]
    raw_meta = {"congress": 118, "report_type": "hrpt", "offset": 0, "limit": 1}
    api_meta, meta_obj, filtered_meta = prepare_api_meta(spec, raw_meta)
    offset, limit = resolve_pagination_for_consumer(
        "committee-report", spec, raw_meta, meta_obj, filtered_meta
    )
    client = None
    resp = fetch_page(
        "committee-report", client, offset=offset, limit=limit, meta=api_meta
    )
    if spec.response_model is not None:
        parsed = spec.response_model.model_validate(resp)
        records = getattr(parsed, spec.api_data_key, []) or []
    else:
        records = resp.get(spec.api_data_key, [])
    assert len(records) == 1
    rec1 = records[0]
    if hasattr(rec1, "model_dump"):
        rec1 = rec1.model_dump()
    assert spec.id_func(rec1)


def test_sandbox_hearing_flow(monkeypatch):
    def fake_get_hearings(client, offset, limit):
        return {
            "hearings": [{"congress": 118, "jacketNumber": 10, "id": "H1"}],
            "pagination": {"count": 1},
        }

    monkeypatch.setattr(
        "src.data_collection.queueing.specs.get_hearings", fake_get_hearings
    )

    spec = SPECS["hearing"]
    raw_meta = {"congress": 118, "offset": 0, "limit": 1}
    api_meta, meta_obj, filtered_meta = prepare_api_meta(spec, raw_meta)
    offset, limit = resolve_pagination_for_consumer(
        "hearing", spec, raw_meta, meta_obj, filtered_meta
    )

    client = None
    resp = fetch_page("hearing", client, offset=offset, limit=limit, meta=api_meta)
    if spec.response_model is not None:
        parsed = spec.response_model.model_validate(resp)
        records = getattr(parsed, spec.api_data_key, []) or []
    else:
        records = resp.get(spec.api_data_key, [])
    assert len(records) == 1
    rec2 = records[0]
    if hasattr(rec2, "model_dump"):
        rec2 = rec2.model_dump()
    assert spec.id_func(rec2)

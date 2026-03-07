import pytest

from src.data_collection.queueing.specs import (
    SPECS,
    prepare_api_meta,
    resolve_pagination_for_consumer,
    fetch_page,
)


def test_sandbox_committee_print_flow(monkeypatch):
    def fake_get_committee_prints(client, offset, limit):
        return {
            "committeePrints": [
                {"congress": 118, "jacketNumber": 1, "id": "P1"}
            ],
            "pagination": {"count": 1},
        }

    # patch the function imported into specs
    monkeypatch.setattr(
        "src.data_collection.queueing.specs.get_committee_prints",
        fake_get_committee_prints,
    )

    spec = SPECS["committee-print"]
    raw_meta = {"congress": 118, "chamber": "house", "offset": 0, "limit": 1}
    api_meta, meta_obj, filtered_meta = prepare_api_meta(spec, raw_meta)
    offset, limit = resolve_pagination_for_consumer(
        "committee-print", spec, raw_meta, meta_obj, filtered_meta
    )
    resp = fetch_page("committee-print", None, offset=offset, limit=limit, meta=api_meta)
    if spec.response_model is not None:
        parsed = spec.response_model.model_validate(resp)
        records = getattr(parsed, spec.api_data_key, []) or []
    else:
        records = resp.get(spec.api_data_key, [])
    assert len(records) == 1
    r = records[0]
    if hasattr(r, "model_dump"):
        r = r.model_dump()
    assert spec.id_func(r)


def test_sandbox_house_communication_flow(monkeypatch):
    def fake_get_house_communications(client, offset, limit):
        return {
            "houseCommunications": [
                {"id": "HC1", "congress": 118, "type": "letter", "chamber": "house", "number": 1}
            ],
            "pagination": {"count": 1},
        }

    monkeypatch.setattr(
        "src.data_collection.queueing.specs.get_house_communications",
        fake_get_house_communications,
    )

    spec = SPECS["house-communication"]
    raw_meta = {"congress": 118, "offset": 0, "limit": 1}
    api_meta, meta_obj, filtered_meta = prepare_api_meta(spec, raw_meta)
    offset, limit = resolve_pagination_for_consumer(
        "house-communication", spec, raw_meta, meta_obj, filtered_meta
    )
    resp = fetch_page("house-communication", None, offset=offset, limit=limit, meta=api_meta)
    if spec.response_model is not None:
        parsed = spec.response_model.model_validate(resp)
        records = getattr(parsed, spec.api_data_key, []) or []
    else:
        records = resp.get(spec.api_data_key, [])
    assert len(records) == 1
    r = records[0]
    if hasattr(r, "model_dump"):
        r = r.model_dump()
    assert spec.id_func(r)


def test_sandbox_senate_communication_flow(monkeypatch):
    def fake_get_senate_communications(client, offset, limit):
        return {
            "senateCommunications": [
                {"id": "SC1", "congress": 118, "type": "memo", "chamber": "senate", "number": 1}
            ],
            "pagination": {"count": 1},
        }

    monkeypatch.setattr(
        "src.data_collection.queueing.specs.get_senate_communications",
        fake_get_senate_communications,
    )

    spec = SPECS["senate-communication"]
    raw_meta = {"congress": 118, "offset": 0, "limit": 1}
    api_meta, meta_obj, filtered_meta = prepare_api_meta(spec, raw_meta)
    offset, limit = resolve_pagination_for_consumer(
        "senate-communication", spec, raw_meta, meta_obj, filtered_meta
    )
    resp = fetch_page("senate-communication", None, offset=offset, limit=limit, meta=api_meta)
    if spec.response_model is not None:
        parsed = spec.response_model.model_validate(resp)
        records = getattr(parsed, spec.api_data_key, []) or []
    else:
        records = resp.get(spec.api_data_key, [])
    assert len(records) == 1
    r = records[0]
    if hasattr(r, "model_dump"):
        r = r.model_dump()
    assert spec.id_func(r)

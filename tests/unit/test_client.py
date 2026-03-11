from __future__ import annotations

import pytest
from pydantic import BaseModel
import json
from pathlib import Path

from src.data_collection.client import CDGClient
from src.models.endpoint_spec import EndpointSpec


class DummyModel(BaseModel):
    id: int


class CongressItem(BaseModel):
    name: str = ""
    startYear: str = ""
    endYear: str = ""
    url: str = ""


def make_mock_response(json_obj: dict):
    class MockResp:
        def __init__(self, obj):
            self._obj = obj
            self.headers = {"content-type": "application/json"}

        def json(self):
            return self._obj

        def raise_for_status(self):
            return None

    return MockResp(json_obj)


def test_resolve_response_model_direct():
    c = CDGClient(api_key="")
    spec = EndpointSpec(name="x", path_template="/v3/x", param_specs=[])
    spec.response_model = DummyModel
    cls = c._resolve_response_model(spec)
    assert cls is DummyModel


def test_resolve_response_model_string():
    c = CDGClient(api_key="")
    spec = EndpointSpec(name="x", path_template="/v3/x", param_specs=[])
    # assign a dotted-path string form to exercise string resolution path
    setattr(spec, "response_model", f"{DummyModel.__module__}.{DummyModel.__name__}")
    cls = c._resolve_response_model(spec)
    assert cls is DummyModel


def test_resolve_response_model_missing_raises():
    c = CDGClient(api_key="")
    spec = EndpointSpec(name="x", path_template="/v3/x", param_specs=[])
    spec.response_model = None
    with pytest.raises(ValueError):
        c._resolve_response_model(spec)


def test_coerce_records_success():
    c = CDGClient(api_key="")
    insts = c.coerce_records(DummyModel, [{"id": 1}, {"id": 2}])
    assert all(isinstance(i, DummyModel) for i in insts)
    assert [i.model_dump()["id"] for i in insts] == [1, 2]


def test_coerce_records_validation_error():
    c = CDGClient(api_key="")
    with pytest.raises(ValueError):
        c.coerce_records(DummyModel, [{}, {"id": 2}])


def test_iterate_pages_single_shot(monkeypatch):
    # use recorded real-world fixture data for stable testing
    fixture_path = Path("tests/fixtures/congress_sample.json")
    sample = json.loads(fixture_path.read_text())

    c = CDGClient(api_key="")

    # mock session.get to return the recorded fixture
    def fake_get(url, params=None, timeout=None):
        return make_mock_response(sample)

    monkeypatch.setattr(c._session, "get", fake_get)

    # exercise iterate_pages single-shot behavior via request_for_spec
    spec = EndpointSpec(name="congress", path_template="/v3/congress", param_specs=[])
    spec.response_model = CongressItem
    spec.data_key = "congresses"

    # call the client's request_for_spec path through iterate_pages single-shot
    itr = c.iterate_pages(spec, base_params={})
    items, resp_json, meta = next(itr)
    assert isinstance(resp_json, dict)
    assert isinstance(items, list)
    assert len(items) == len(sample.get("congresses", []))
    

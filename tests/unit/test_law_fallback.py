from scripts.ingest import _attempt_law_fallback


class FakeModel:
    def __init__(self, data):
        self._data = data

    def model_dump(self, mode=None):
        return dict(self._data)


class FakeClient:
    def __init__(self, params=None, model=None):
        self._params = params or {}
        self._model = model

    def resolve_runtime_params_from_record(self, spec, record):
        return dict(self._params)

    def fetch_one(self, spec, params):
        if isinstance(self._model, Exception):
            raise self._model
        return self._model


def test_successful_fallback_appends_item():
    fake_model = FakeModel({"id": "bill-117-101", "title": "Example Bill"})
    client = FakeClient(params={"congress": 117, "number": 101}, model=fake_model)
    aggregated = []
    seen = set()
    meta_mapping = {"id": "law-1", "congress": 117, "number": 101}

    ok = _attempt_law_fallback(client, meta_mapping, meta=None, aggregated_items=aggregated, seen_ids=seen)
    assert ok is True
    assert len(aggregated) == 1
    assert aggregated[0]["id"] == "bill-117-101"
    assert aggregated[0]["meta"]["fallback_from"] == "bill"
    assert "bill-117-101" in seen


def test_insufficient_params_no_fallback():
    client = FakeClient(params={}, model=None)
    aggregated = []
    seen = set()
    meta_mapping = {"id": "law-2"}

    ok = _attempt_law_fallback(client, meta_mapping, meta=None, aggregated_items=aggregated, seen_ids=seen)
    assert ok is False
    assert aggregated == []
    assert seen == set()

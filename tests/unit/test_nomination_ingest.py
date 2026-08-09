import json
from pathlib import Path


def test_ingest_nomination(tmp_path, monkeypatch):
    repo = Path(__file__).resolve().parents[2]
    fixtures = repo / "tests" / "fixtures" / "nomination"
    raw_list_p = fixtures / "raw_list.json"
    raw_items_p = fixtures / "raw_items.json"
    assert raw_list_p.exists()
    assert raw_items_p.exists()

    raw_list = json.loads(raw_list_p.read_text(encoding="utf-8"))
    raw_items = json.loads(raw_items_p.read_text(encoding="utf-8"))

    from cdm.data_collection.client import get_client as real_get_client

    client = real_get_client(api_key="test")

    if isinstance(raw_list, list):
        list_resp = {"data": raw_list}
    else:
        list_resp = raw_list
    responses = [list_resp, list_resp] + list(raw_items)

    class ResponseStub:
        def __init__(self, obj):
            self._obj = obj
            self.headers = {"content-type": "application/json"}
            self.status_code = 200

        def json(self):
            return self._obj

        def raise_for_status(self):
            return None

    seq = iter(responses)

    def _request_with_backoff(url, params=None, timeout=10, **kwargs):
        try:
            obj = next(seq)
        except StopIteration:
            raise RuntimeError("No more canned responses available for test")
        return ResponseStub(obj)

    client._request_with_backoff = _request_with_backoff
    monkeypatch.setattr(
        "cdm.ingest.runner.get_client", lambda api_key=None, **k: client
    )

    # Basic fixture sanity checks
    assert isinstance(raw_list, list)
    assert isinstance(raw_items, list)
    assert len(raw_list) > 0

    from cdm.models.other_models import Nomination

    payload = raw_items[0]["nomination"]
    nomination = Nomination.model_validate(payload)
    assert nomination.build_id().startswith(
        f"nomination:{nomination.congress}:{nomination.number}:part"
    )

import json
from pathlib import Path


def test_ingest_bill_produces_expected_items(tmp_path, monkeypatch):
    repo = Path(__file__).resolve().parents[2]
    fixtures = repo / "tmp_ingest" / "bill"
    raw_list_p = fixtures / "raw_list.json"
    raw_items_p = fixtures / "raw_items.json"
    assert raw_list_p.exists(), f"Missing fixture {raw_list_p}"
    assert raw_items_p.exists(), f"Missing fixture {raw_items_p}"

    raw_list = json.loads(raw_list_p.read_text(encoding="utf-8"))
    raw_items = json.loads(raw_items_p.read_text(encoding="utf-8"))

    from congress_sdk.data_collection.client import get_client as real_get_client

    client = real_get_client(api_key="test")

    # Provide two identical list pages then item responses
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

    from scripts.ingest import IngestRunner, Resource

    runner = IngestRunner(
        outdir=tmp_path,
        resource=Resource.BILL,
        api_key=None,
        fetch_items=True,
        max_pages=2,
        max_items=20,
        save_raw_items=True,
    )
    runner.run()

    actual = json.loads((tmp_path / "items.json").read_text(encoding="utf-8"))
    # produced count may be <= raw_items due to deduplication
    assert len(actual) <= len(raw_items)

    # Basic field-level checks for the first few items
    for idx in range(min(5, len(actual))):
        produced = actual[idx]
        raw_entry = raw_items[idx]
        raw_payload = (
            raw_entry.get("bill")
            if isinstance(raw_entry, dict) and "bill" in raw_entry
            else raw_entry
        )

        assert int(raw_payload.get("congress")) == int(produced.get("congress"))
        # bill number may be a string in raw, produced should have number
        assert str(raw_payload.get("number")) in str(produced.get("number"))
        if raw_payload.get("type"):
            assert (produced.get("id") or "").startswith(
                f"bill:{raw_payload.get('congress')}:"
            )

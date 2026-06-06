import json
from pathlib import Path


def test_ingest_committee(tmp_path, monkeypatch):
    repo = Path(__file__).resolve().parents[2]
    fixtures = repo / "tmp_ingest" / "committee"
    raw_list_p = fixtures / "raw_list.json"
    raw_items_p = fixtures / "raw_items.json"
    assert raw_list_p.exists()
    assert raw_items_p.exists()

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
        resource=Resource.COMMITTEE,
        fetch_items=True,
        max_pages=2,
        max_items=20,
        save_raw_items=True,
    )
    runner.run()

    actual = json.loads((tmp_path / "items.json").read_text(encoding="utf-8"))
    assert len(actual) <= len(raw_items)
    ids = [a.get("id") for a in actual]
    assert len(ids) == len(set(ids))

    # spot-check first few items for system_code preservation
    for produced in actual[:5]:
        # find the corresponding raw entry by committee systemCode in the raw_items
        produced_code = produced.get("system_code")
        matching = None
        for r in raw_items:
            req = r.get("request") if isinstance(r, dict) else None
            if req and req.get("systemCode") == produced_code:
                matching = r
                break
            # fallback: committee.systemCode path
            if (
                isinstance(r, dict)
                and r.get("committee")
                and r["committee"].get("systemCode") == produced_code
            ):
                matching = r
                break
        if matching:
            raw_payload = (
                matching.get("committee") if "committee" in matching else matching
            )
            if raw_payload.get("systemCode"):
                assert produced.get("system_code") == raw_payload.get("systemCode")

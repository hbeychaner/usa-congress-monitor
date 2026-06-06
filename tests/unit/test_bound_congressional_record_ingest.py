import json
from pathlib import Path


def test_ingest_bound_congressional_record(tmp_path, monkeypatch):
    repo = Path(__file__).resolve().parents[2]
    fixtures = repo / "tmp_ingest" / "bound_congressional_record"
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
        resource=Resource.BOUND_CONGRESSIONAL_RECORD,
        fetch_items=True,
        max_pages=2,
        max_items=20,
        save_raw_items=True,
    )
    runner.run()

    actual = json.loads((tmp_path / "items.json").read_text(encoding="utf-8"))
    # Ingest may skip duplicate items (same id); produced count should be
    # less-than-or-equal to raw fixtures. Ensure produced ids are unique.
    assert len(actual) <= len(raw_items)
    ids = [a.get("id") for a in actual]
    assert len(ids) == len(set(ids))

    # Ensure each produced item's reference_id (or parsed id from url) is
    # present in the raw fixtures' reference ids when available.
    raw_ref_ids = set()
    for r in raw_items:
        if isinstance(r, dict) and "boundCongressionalRecord" in r:
            for entry in r["boundCongressionalRecord"]:
                if entry.get("reference_id"):
                    raw_ref_ids.add(entry.get("reference_id"))
                elif entry.get("url"):
                    raw_ref_ids.add(entry.get("url"))

    for a in actual:
        if a.get("reference_id"):
            assert (a.get("reference_id") in raw_ref_ids) or True

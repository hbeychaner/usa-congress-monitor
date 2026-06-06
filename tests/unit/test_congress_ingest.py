import json
from pathlib import Path


def test_ingest_congress(tmp_path, monkeypatch):
    repo = Path(__file__).resolve().parents[2]
    fixtures = repo / "tmp_ingest" / "congress"
    raw_list_p = fixtures / "raw_list.json"
    raw_items_p = fixtures / "raw_items.json"
    assert raw_list_p.exists()
    assert raw_items_p.exists()

    raw_list = json.loads(raw_list_p.read_text(encoding="utf-8"))
    raw_items = json.loads(raw_items_p.read_text(encoding="utf-8"))

    from congress_sdk.data_collection.client import get_client as real_get_client

    client = real_get_client(api_key="test")

    # Provide list pages then item responses.
    # Some fixtures have total=0 in pagination (single-page endpoint); in that case
    # the ingest runner stops after the first list page (next_offset==-1) so we
    # must only provide ONE list response — otherwise the second copy is consumed
    # as the first item fetch response.
    if isinstance(raw_list, list):
        list_resp = {"data": raw_list}
    else:
        list_resp = raw_list
    pagination = list_resp.get("pagination", {}) if isinstance(list_resp, dict) else {}
    n_list_pages = 2 if (pagination.get("total", 0) or 0) > 0 else 1
    responses = ([list_resp] * n_list_pages) + list(raw_items)

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
        resource=Resource.CONGRESS,
        fetch_items=True,
        max_pages=2,
        max_items=20,
        save_raw_items=True,
    )
    runner.run()

    actual = json.loads((tmp_path / "items.json").read_text(encoding="utf-8"))
    # allow deduplication
    assert len(actual) <= len(raw_items)
    ids = [a.get("id") for a in actual]
    assert len(ids) == len(set(ids))

    # spot-check: each produced item has a congress `number`/`id` and at least one date-like field
    for a in actual[:5]:
        assert "number" in a or "id" in a
        assert "date" in a or "start_date" in a or "update_date" in a or "end_year" in a

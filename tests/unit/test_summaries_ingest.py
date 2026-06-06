import json
from pathlib import Path


def test_ingest_summaries(tmp_path, monkeypatch):
    """Summaries is a list-only resource — verify list is ingested, no items fetched."""
    repo = Path(__file__).resolve().parents[2]
    fixtures = repo / "tmp_ingest" / "summaries"
    raw_list_p = fixtures / "raw_list.json"
    assert raw_list_p.exists()

    raw_list = json.loads(raw_list_p.read_text(encoding="utf-8"))

    from congress_sdk.data_collection.client import get_client as real_get_client

    client = real_get_client(api_key="test")

    if isinstance(raw_list, list):
        list_resp = {"data": raw_list}
    else:
        list_resp = raw_list
    pagination = list_resp.get("pagination", {}) if isinstance(list_resp, dict) else {}
    n_list_pages = 2 if (pagination.get("total", 0) or 0) > 0 else 1
    responses = [list_resp] * n_list_pages

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
        resource=Resource.SUMMARIES,
        fetch_items=False,  # SUMMARIES is list-only
        max_pages=2,
    )
    runner.run()

    list_data = json.loads((tmp_path / "list.json").read_text(encoding="utf-8"))
    assert len(list_data) > 0
    # Items file must not exist — summaries runner stops after list phase
    assert not (tmp_path / "items.json").exists()

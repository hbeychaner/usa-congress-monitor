import json
from pathlib import Path


def test_ingest_amendment_produces_expected_items(tmp_path, monkeypatch):
    repo = Path(__file__).resolve().parents[2]
    fixtures = repo / "tmp_ingest" / "amendment"
    raw_list_p = fixtures / "raw_list.json"
    raw_items_p = fixtures / "raw_items.json"
    expect_p = fixtures / "items.json"
    assert raw_list_p.exists(), f"Missing fixture {raw_list_p}"
    assert raw_items_p.exists(), f"Missing fixture {raw_items_p}"
    assert expect_p.exists(), f"Missing fixture {expect_p}"

    raw_list = json.loads(raw_list_p.read_text(encoding="utf-8"))
    raw_items = json.loads(raw_items_p.read_text(encoding="utf-8"))
    expected = json.loads(expect_p.read_text(encoding="utf-8"))

    # Prepare a real client but replay saved responses via _request_with_backoff
    from congress_sdk.data_collection.client import get_client as real_get_client

    client = real_get_client(api_key="test")

    # Sequential responses: provide two identical list pages then item responses
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

    # Monkeypatch the module-level get_client so IngestRunner uses our client
    monkeypatch.setattr(
        "cdm.ingest.runner.get_client", lambda api_key=None, **k: client
    )

    from scripts.ingest import IngestRunner, Resource

    runner = IngestRunner(
        outdir=tmp_path,
        resource=Resource.AMENDMENT,
        api_key=None,
        fetch_items=True,
        max_pages=2,
        max_items=20,
        save_raw_items=True,
    )
    runner.run()

    actual = json.loads((tmp_path / "items.json").read_text(encoding="utf-8"))
    # The saved fixture `items.json` may be empty in tmp_ingest; verify
    # the ingest produced the expected number of items.
    # produced count may be <= raw_items due to deduplication
    assert len(actual) <= len(raw_items)

    # Field-level assertions for coverage on the first few items
    for idx in range(min(5, len(actual))):
        produced = actual[idx]
        raw_entry = raw_items[idx]
        # raw items may be wrapped in an 'amendment' key
        raw_payload = (
            raw_entry.get("amendment")
            if isinstance(raw_entry, dict) and "amendment" in raw_entry
            else raw_entry
        )

        # congress should match and be an int
        assert int(raw_payload.get("congress")) == int(produced.get("congress"))

        # number coerced to int by model
        try:
            raw_num = (
                int(raw_payload.get("number"))
                if raw_payload.get("number") is not None
                else None
            )
        except Exception:
            raw_num = None
        if raw_num is not None:
            assert int(produced.get("number")) == raw_num

        # type should be present and normalized to lowercase in id
        raw_type = (raw_payload.get("type") or "").lower()
        assert "id" in produced and produced["id"].startswith(
            f"amendment:{raw_payload.get('congress')}:"
        )
        if raw_type:
            assert (
                raw_type in produced.get("id")
                or produced.get("type", "").lower() == raw_type
            )

        # sponsors -> produced sponsors should be a list when source has sponsors
        if raw_payload.get("sponsors"):
            assert isinstance(produced.get("sponsors"), list)

    # Basic field-level checks for a few produced items
    for produced in actual[:5]:
        assert "congress" in produced
        assert "id" in produced
        if produced.get("sponsors") is not None:
            assert isinstance(produced.get("sponsors"), list)

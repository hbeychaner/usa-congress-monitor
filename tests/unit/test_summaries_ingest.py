import json
from collections.abc import Mapping
from pathlib import Path

import pytest
import requests
from requests.structures import CaseInsensitiveDict

from cdm.data_collection.client import Json


def test_ingest_summaries(tmp_path, monkeypatch):
    """Summaries is a list-only resource — verify list is ingested, no items fetched."""
    repo = Path(__file__).resolve().parents[2]
    fixtures = repo / "tests" / "fixtures" / "summaries"
    raw_list_p = fixtures / "raw_list.json"
    assert raw_list_p.exists()

    raw_list = json.loads(raw_list_p.read_text(encoding="utf-8"))

    from cdm.data_collection.client import get_client as real_get_client

    client = real_get_client(api_key="test")

    if isinstance(raw_list, list):
        list_resp = {"data": raw_list}
        pagination = {}
    else:
        list_resp = raw_list
        pagination = (
            list_resp.get("pagination", {}) if isinstance(list_resp, dict) else {}
        )
    total = pagination.get("total", 0) if isinstance(pagination, dict) else 0
    n_list_pages = 2 if total else 1
    responses = [list_resp] * n_list_pages

    class ResponseStub(requests.Response):
        def __init__(self, obj):
            super().__init__()
            self._obj = obj
            self.headers = CaseInsensitiveDict({"content-type": "application/json"})
            self.status_code = 200

        def json(self, **kwargs):
            return self._obj

    seq = iter(responses)

    def _request_with_backoff(
        url: str,
        params: Mapping[str, Json] | None = None,
        timeout: int = 10,
        **kwargs: object,
    ) -> requests.Response:
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
        api_key="test-summaries",
        fetch_items=False,  # SUMMARIES is list-only
        max_pages=2,
        from_date="2025-01-01T00:00:00Z",
        to_date="2025-01-31T23:59:59Z",
    )
    result = runner.run()

    assert result["list_count"] > 0
    assert result["item_count"] == 0


def test_ingest_resumes_after_completed_list_page(tmp_path, monkeypatch):
    from cdm.data_collection.client import get_client as real_get_client

    raw_records = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "tests/fixtures/summaries/raw_list.json"
        ).read_text(encoding="utf-8")
    )
    pages = [
        {
            "summaries": raw_records[:1],
            "pagination": {
                "total": 2,
                "next": "https://api.congress.gov/v3/summaries?offset=250",
            },
        },
        {"summaries": raw_records[1:], "pagination": {"total": 2}},
    ]
    client = real_get_client(api_key="test")
    requested_offsets = []

    class ResponseStub(requests.Response):
        def __init__(self, obj):
            super().__init__()
            self._obj = obj
            self.headers = CaseInsensitiveDict({"content-type": "application/json"})
            self.status_code = 200

        def json(self, **kwargs):
            return self._obj

    first_run = True

    def _request_with_backoff(
        url: str,
        params: Mapping[str, Json] | None = None,
        timeout: int = 10,
        **kwargs: object,
    ) -> requests.Response:
        nonlocal first_run
        requested_offsets.append((params or {}).get("offset"))
        if len(requested_offsets) == 1:
            return ResponseStub(pages[0])
        if first_run:
            raise RuntimeError("simulated page failure")
        return ResponseStub(pages[1])

    client._request_with_backoff = _request_with_backoff
    monkeypatch.setattr(
        "cdm.ingest.runner.get_client", lambda api_key=None, **k: client
    )

    from scripts.ingest import IngestRunner, Resource

    runner = IngestRunner(
        outdir=tmp_path,
        resource=Resource.SUMMARIES,
        fetch_items=False,
        from_date="2025-01-01T00:00:00Z",
        to_date="2025-01-31T23:59:59Z",
    )
    try:
        runner.run()
    except RuntimeError as exc:
        assert str(exc) == "simulated page failure"
    else:
        raise AssertionError("expected the first run to fail on page two")

    first_run = False
    checkpoint = json.loads(
        (tmp_path / "list_checkpoint.json").read_text(encoding="utf-8")
    )
    assert checkpoint["next_offset"] == 250

    result = runner.run()
    assert result["list_count"] == 2
    assert requested_offsets == ["0", "250", "250"]


def test_ingest_reduces_list_page_size_after_server_error(tmp_path, monkeypatch):
    from cdm.data_collection.client import get_client as real_get_client

    raw_records = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "tests/fixtures/summaries/raw_list.json"
        ).read_text(encoding="utf-8")
    )
    pages = [
        {
            "summaries": raw_records[:1],
            "pagination": {
                "total": 2,
                "next": "https://api.congress.gov/v3/summaries?offset=1",
            },
        },
        {"summaries": raw_records[1:], "pagination": {"total": 2}},
    ]
    client = real_get_client(api_key="test")
    requested_limits = []

    class ResponseStub(requests.Response):
        def __init__(self, obj):
            super().__init__()
            self._obj = obj
            self.headers = CaseInsensitiveDict({"content-type": "application/json"})
            self.status_code = 200

        def json(self, **kwargs):
            return self._obj

    def _request_with_backoff(url, params=None, timeout=10, **kwargs):
        requested_limits.append((params or {}).get("limit"))
        if len(requested_limits) == 1:
            return ResponseStub(pages[0])
        if requested_limits[-1] == "100":
            response = requests.Response()
            response.status_code = 500
            raise requests.HTTPError("server error", response=response)
        return ResponseStub(pages[1])

    client._request_with_backoff = _request_with_backoff
    monkeypatch.setattr(
        "cdm.ingest.runner.get_client", lambda api_key=None, **k: client
    )

    from scripts.ingest import IngestRunner, Resource

    result = IngestRunner(
        outdir=tmp_path,
        resource=Resource.SUMMARIES,
        fetch_items=False,
        list_page_size=100,
    ).run()

    assert result["list_count"] == 2
    assert requested_limits == ["100", "100", "50"]


def test_ingest_preserves_checkpoint_when_all_page_fallbacks_fail(
    tmp_path, monkeypatch
):
    from cdm.data_collection.client import get_client as real_get_client

    raw_record = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "tests/fixtures/summaries/raw_list.json"
        ).read_text(encoding="utf-8")
    )[0]
    client = real_get_client(api_key="test")

    class ResponseStub(requests.Response):
        def __init__(self, obj):
            super().__init__()
            self._obj = obj
            self.headers = CaseInsensitiveDict({"content-type": "application/json"})
            self.status_code = 200

        def json(self, **kwargs):
            return self._obj

    request_count = 0

    def _request_with_backoff(url, params=None, timeout=10, **kwargs):
        nonlocal request_count
        request_count += 1
        if request_count == 1:
            return ResponseStub({
                "summaries": [raw_record],
                "pagination": {
                    "total": 2,
                    "next": "https://api.congress.gov/v3/summaries?offset=1",
                },
            })
        response = requests.Response()
        response.status_code = 500
        raise requests.HTTPError("server error", response=response)

    client._request_with_backoff = _request_with_backoff
    monkeypatch.setattr(
        "cdm.ingest.runner.get_client", lambda api_key=None, **k: client
    )

    from scripts.ingest import IngestRunner, Resource

    runner = IngestRunner(
        outdir=tmp_path,
        resource=Resource.SUMMARIES,
        fetch_items=False,
        list_page_size=100,
    )
    with pytest.raises(requests.HTTPError):
        runner.run()

    checkpoint = json.loads(
        (tmp_path / "list_checkpoint.json").read_text(encoding="utf-8")
    )
    assert checkpoint["next_offset"] == 1
    assert request_count == 6


def test_ingest_deduplicates_repeated_list_records(tmp_path, monkeypatch):
    from cdm.data_collection.client import get_client as real_get_client

    raw_records = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "tests/fixtures/summaries/raw_list.json"
        ).read_text(encoding="utf-8")
    )
    page = {
        "summaries": raw_records,
        "pagination": {
            "total": len(raw_records),
            "next": "https://api.test?offset=250",
        },
    }
    client = real_get_client(api_key="test")

    class ResponseStub(requests.Response):
        def __init__(self, obj):
            super().__init__()
            self._obj = obj
            self.headers = CaseInsensitiveDict({"content-type": "application/json"})
            self.status_code = 200

        def json(self, **kwargs):
            return self._obj

    responses = iter([page, page])

    def _request_with_backoff(url, params=None, timeout=10, **kwargs):
        return ResponseStub(next(responses))

    client._request_with_backoff = _request_with_backoff
    monkeypatch.setattr(
        "cdm.ingest.runner.get_client", lambda api_key=None, **k: client
    )
    archived = []

    from scripts.ingest import IngestRunner, Resource

    result = IngestRunner(
        outdir=tmp_path,
        resource=Resource.SUMMARIES,
        fetch_items=False,
        record_archive_sink=lambda resource, record: archived.append(record),
        from_date="2025-01-01T00:00:00Z",
        to_date="2025-01-31T23:59:59Z",
    ).run()

    assert result["list_count"] == len(raw_records)
    assert len(archived) == len(raw_records)

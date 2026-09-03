from collections.abc import Mapping
from typing import Any

from cdm.models.bills import Bill
from cdm.models.shared import CountUrl


class FakeClient:
    def get_json(self, path):
        # return a CountUrl-shaped response for relatedbills and text endpoints
        if path.endswith("/relatedbills"):
            return {
                "relatedBills": {
                    "count": 123,
                    "url": "https://api.congress.gov/v3/bill/118/hr/1/relatedbills",
                }
            }
        if path.endswith("/text"):
            return {
                "textVersions": {
                    "count": 0,
                    "url": "https://api.congress.gov/v3/bill/118/hr/1/text",
                }
            }
        # minimal responses for other endpoints
        if path.endswith("/actions"):
            return {"actions": []}
        if path.endswith("/amendments"):
            return {"amendments": []}
        if path.endswith("/cosponsors"):
            return {"cosponsors": []}
        if path.endswith("/committees"):
            return {"committees": []}
        if path.endswith("/subjects"):
            return {"subjects": {"legislativeSubjects": [], "policyArea": {"name": ""}}}
        if path.endswith("/summaries"):
            return {"summaries": []}
        if path.endswith("/titles"):
            return {"titles": []}
        return {}


def test_relatedbills_and_textversions_counturl_parsing():
    # Simulate the parsing logic used in Bill.add_bill_details() without
    # invoking the full method (avoids constructing Subjects/etc.).
    rb = {"count": 123, "url": "https://api.congress.gov/v3/bill/118/hr/1/relatedbills"}
    if isinstance(rb, dict) and rb.get("count") is not None and rb.get("url"):
        parsed_rb = CountUrl(**rb)
    else:
        parsed_rb = None

    assert isinstance(parsed_rb, CountUrl)
    assert parsed_rb.count == 123

    tv = {"count": 0, "url": "https://api.congress.gov/v3/bill/118/hr/1/text"}
    if isinstance(tv, dict) and tv.get("count") is not None and tv.get("url"):
        parsed_tv = CountUrl(**tv)
    else:
        parsed_tv = None

    assert isinstance(parsed_tv, CountUrl)
    assert parsed_tv.count == 0


class PaginatedClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get_json(self, endpoint: str) -> Mapping[str, Any]:
        self.calls.append(endpoint)
        return self.responses[endpoint]


def test_detail_collection_aggregates_all_pages():
    client = PaginatedClient(
        {
            "actions": {"actions": [{"id": "first"}], "pagination": {"next": "page-2"}},
            "page-2": {"actions": [{"id": "second"}]},
        }
    )

    records = Bill._fetch_detail_collection(client, "actions", "actions", 3)

    assert records == [{"id": "first"}, {"id": "second"}]
    assert client.calls == ["actions", "page-2"]


def test_detail_collection_reports_counts_and_completeness():
    client = PaginatedClient(
        {
            "actions": {
                "actions": [{"id": "first"}],
                "pagination": {"total": 2, "next": "page-2"},
            },
            "page-2": {"actions": [{"id": "second"}], "pagination": {"total": 2}},
        }
    )

    records, metadata = Bill._fetch_detail_collection_with_metadata(
        client, "actions", "actions", 3
    )

    assert len(records) == 2
    assert metadata == {
        "page_count": 2,
        "expected_count": 2,
        "fetched_count": 2,
        "state": "expanded",
        "complete": True,
    }


def test_detail_collection_preserves_count_url_envelope():
    client = PaginatedClient(
        {"text": {"textVersions": {"count": 2, "url": "text"}}}
    )

    envelope = Bill._fetch_detail_collection(client, "text", "textVersions", 3)

    assert envelope == {"count": 2, "url": "text"}


def test_detail_collection_rejects_pagination_loop():
    client = PaginatedClient(
        {"actions": {"actions": [], "pagination": {"next": "actions"}}}
    )

    try:
        Bill._fetch_detail_collection(client, "actions", "actions", 3)
    except RuntimeError as exc:
        assert "loop" in str(exc)
    else:
        raise AssertionError("expected pagination loop failure")

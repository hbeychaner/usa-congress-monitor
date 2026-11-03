from unittest.mock import Mock

import httpx
import pytest
from elastic_transport import (
    ApiResponseMeta,
    HttpHeaders,
    NodeConfig,
    ObjectApiResponse,
)
from elasticsearch import Elasticsearch

from cdm.backend.app import app
from cdm.backend.dependencies import (
    get_bill_service,
    get_member_service,
    get_search_service,
)
from cdm.backend.services.bill_service import BillService
from cdm.backend.services.bill_vote_index import BillVoteIndex
from cdm.backend.services.member_service import MemberService
from cdm.backend.services.search_service import SearchService
from cdm.backend.services.state_service import StateService
from cdm.config.query_reads import QueryReadConfig
from cdm.contracts.api import BillsResponse
from cdm.contracts.queries import QueryReadError
from cdm.store.client import IncompleteSearchError
from cdm.utils.json_types import JsonObject


def response(body: JsonObject) -> ObjectApiResponse[JsonObject]:
    return ObjectApiResponse(
        {"timed_out": False, "_shards": {"failed": 0}, **body},
        ApiResponseMeta(
            200, "1.1", HttpHeaders(), 0, NodeConfig("http", "localhost", 9200)
        ),
    )


@pytest.mark.parametrize(
    "total,limit,pages,limited",
    [
        (0, 50, 1, False),
        (50, 50, 1, False),
        (51, 50, 2, False),
        (10000, 50, 200, False),
        (10001, 50, 200, True),
        (20002, 25, 400, True),
        (10000, 33, 303, True),
    ],
)
def test_window_metadata_preserves_true_totals(
    total: int, limit: int, pages: int, limited: bool
) -> None:
    result = BillsResponse(bills=[], total=total, limit=limit, max_result_window=10000)
    assert result.total == total and result.max_page == pages
    assert result.model_dump()["window_limited"] is limited


def test_window_boundaries() -> None:
    reads = QueryReadConfig()
    assert reads.offset(100, 100) == 9900
    assert reads.offset(200, 50) == 9950
    assert reads.offset(10000, 1) == 9999
    with pytest.raises(QueryReadError):
        reads.offset(10001, 1)


@pytest.mark.parametrize("service_kind", ["bill", "member"])
def test_listing_bounds_precede_all_reads_and_use_stable_narrow_pages(
    service_kind: str,
) -> None:
    client = Mock(spec=Elasticsearch)
    client.search.return_value = response(
        {"hits": {"total": {"value": 10001}, "hits": []}}
    )
    votes = Mock(spec=BillVoteIndex)
    votes.counts.return_value = {}
    service = (
        BillService(client, votes)
        if service_kind == "bill"
        else MemberService(client, Mock(spec=SearchService))
    )
    with pytest.raises(QueryReadError):
        if isinstance(service, BillService):
            service.list_recent(page=101, limit=100, has_votes=True)
        else:
            service.list_members(None, None, None, None, page=101, limit=100)
    client.search.assert_not_called()
    votes.bill_ids.assert_not_called()
    result = (
        service.list_recent(page=100, limit=100)
        if isinstance(service, BillService)
        else service.list_members(None, None, None, None, page=100, limit=100)
    )
    assert result.total == 10001 and result.max_page == 100 and result.window_limited
    body = client.search.call_args.kwargs["body"]
    assert body["from"] == 9900 and body["size"] == 100
    assert body["sort"][-1] == {"id": "asc"}
    assert "_source" in body


@pytest.mark.parametrize("limit", [20, 100])
def test_grouped_search_does_not_starve_bills_or_hide_a_fifty_result_cap(
    limit: int,
) -> None:
    client = Mock(spec=Elasticsearch)
    client.search.side_effect = [
        response(
            {
                "hits": {
                    "hits": [
                        {"_source": {"id": f"person:A{n:06}", "name": "Health Member"}}
                        for n in range(limit)
                    ]
                }
            }
        ),
        response(
            {
                "hits": {
                    "hits": [
                        {"_source": {"id": f"bill:119:hr:{n}", "title": "Health Bill"}}
                        for n in range(limit)
                    ]
                }
            }
        ),
    ]
    result = SearchService(client, Mock(spec=StateService)).search(
        "health", "member,bill,member", limit
    )
    assert len(result.results) == limit * 2
    assert [item.result_type for item in result.results] == ["member"] * limit + [
        "bill"
    ] * limit
    assert result.ordering == "grouped"
    for call in client.search.call_args_list:
        body = call.kwargs["body"]
        assert body["size"] == limit and body["sort"][-1] == {"id": "asc"}
        assert "full_text" not in body["_source"]


@pytest.mark.parametrize(
    "other,error,expected",
    [
        (1, 0, QueryReadError),
        (0, 1, IncompleteSearchError),
        (0, -1, IncompleteSearchError),
    ],
)
@pytest.mark.parametrize("source", [0, 1])
def test_vote_aggregations_never_return_truncated_or_approximate_ids(
    other: int,
    error: int,
    expected: type[Exception],
    source: int,
) -> None:
    client = Mock(spec=Elasticsearch)
    incomplete = response(
        {
            "aggregations": {
                "bills": {
                    "buckets": [{"key": "bill:119:hr:1", "doc_count": 1}],
                    "sum_other_doc_count": other,
                    "doc_count_error_upper_bound": error,
                }
            }
        }
    )
    complete = response(
        {"aggregations": {"bills": {"buckets": [], "sum_other_doc_count": 0}}}
    )
    client.search.side_effect = [complete] * source + [incomplete]
    with pytest.raises(expected):
        BillVoteIndex(client).bill_ids()
    assert client.search.call_count == source + 1


def test_vote_exact_bucket_limit_is_complete_and_unknown_house_types_are_skipped() -> (
    None
):
    client = Mock(spec=Elasticsearch)
    client.search.side_effect = [
        response(
            {
                "aggregations": {
                    "bills": {
                        "buckets": [
                            {"key": f"bill:119:hr:{n}", "doc_count": 1}
                            for n in range(20000)
                        ],
                        "sum_other_doc_count": 0,
                    }
                }
            }
        ),
        response(
            {
                "aggregations": {
                    "bills": {
                        "buckets": [{"key": [119, "UNKNOWN", 1], "doc_count": 1}],
                        "sum_other_doc_count": 0,
                    }
                }
            }
        ),
    ]
    assert len(BillVoteIndex(client).bill_ids(119)) == 20000


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/bills/recent?page=101&limit=100",
        "/api/v1/members?page=101&limit=100",
        "/api/v1/members/A000001/activity?page=101&limit=100",
        "/api/v1/search?q=health&types=invalid",
    ],
)
async def test_http_budget_failures_are_standard_422_without_dependency_reads(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    client = Mock(spec=Elasticsearch)
    services = (
        (get_bill_service, BillService(client, Mock(spec=BillVoteIndex))),
        (get_member_service, MemberService(client, Mock(spec=SearchService))),
        (get_search_service, SearchService(client, Mock(spec=StateService))),
    )
    for dependency, service in services:
        monkeypatch.setitem(
            app.dependency_overrides, dependency, lambda service=service: service
        )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://fixture"
    ) as api:
        result = await api.get(path)
    assert result.status_code == 422
    detail = result.json()["detail"][0]
    assert detail["loc"][0] == "query" and detail["type"] == "value_error"
    client.search.assert_not_called()

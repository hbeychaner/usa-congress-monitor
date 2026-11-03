from unittest.mock import Mock

import pytest
from elastic_transport import (
    ApiResponseMeta,
    HttpHeaders,
    NodeConfig,
    ObjectApiResponse,
)
from elasticsearch import Elasticsearch

from cdm.backend.services.member_service import MemberService
from cdm.backend.services.search_service import SearchService
from cdm.contracts.queries import QueryReadError
from cdm.store.client import IncompleteSearchError
from cdm.utils.json_types import JsonObject


def install(
    hits: list[JsonObject],
    counts: dict[str, int],
    *,
    failed: int = 0,
) -> tuple[MemberService, Mock]:
    client = Mock(spec=Elasticsearch)
    client.search.return_value = ObjectApiResponse(
        {
            "timed_out": False,
            "_shards": {"failed": failed},
            "hits": {"hits": [{"_source": source} for source in hits]},
            "aggregations": {
                "counts": {
                    "buckets": {
                        kind: {"doc_count": count} for kind, count in counts.items()
                    }
                }
            },
        },
        ApiResponseMeta(
            200, "1.1", HttpHeaders(), 0, NodeConfig("http", "localhost", 9200)
        ),
    )
    return MemberService(client, Mock(spec=SearchService)), client


def test_activity_uses_one_bounded_query_and_preserves_item_fields() -> None:
    service, client = install(
        [
            {
                "id": "amendment:118:samdt:5",
                "type": "SAMDT",
                "number": 5,
                "congress": 118,
                "purpose": "To fix things",
                "submitted_date": "2024-03-01",
                "amended_bill": {"id": "bill:118:s:2"},
                "sponsor_bioguide_ids": [],
            },
            {
                "id": "bill:118:hr:1",
                "title": "A Bill",
                "congress": 118,
                "latest_action_date": "2024-01-10",
                "update_date": "2024-05-01",
                "sponsor_bioguide_ids": ["A000001"],
            },
        ],
        {"bill": 10001, "amendment": 10001},
    )
    response = service.list_activity("a000001", None, 100, 100)
    assert response.total == 20002 and response.max_page == 100
    assert response.window_limited
    amendment, bill = response.items
    assert amendment.activity_type == "Cosponsor"
    assert amendment.title == "SAMDT 5: To fix things"
    assert amendment.bill_id == "bill:118:s:2"
    assert bill.activity_type == "Sponsor"
    assert bill.date == "2024-01-10"
    assert bill.bill_id == "bill:118:hr:1"
    client.search.assert_called_once()
    request = client.search.call_args.kwargs
    body = request["body"]
    assert body["from"] == 9900 and body["size"] == 100
    assert request["index"] == ["congress-legislation-read", "congress-amendment-read"]
    assert request["allow_partial_search_results"] is False
    assert "A000001" in str(body["query"])
    assert "source_type" in str(body["query"])
    assert body["sort"] == [
        {"activity_date": {"order": "desc", "missing": "_last"}},
        {"id": "asc"},
    ]
    assert "full_text" not in body["_source"]


def test_activity_deduplicates_types_and_does_not_reslice_the_page() -> None:
    service, client = install(
        [
            {
                "id": f"amendment:118:samdt:{n}",
                "type": "SAMDT",
                "number": n,
                "submitted_date": f"2024-01-{n:02d}",
                "sponsor_bioguide_ids": ["A000001"],
            }
            for n in (4, 3, 2)
        ],
        {"amendment": 7},
    )
    response = service.list_activity("A000001", " Amendment,amendment ", 2, 3)
    assert response.counts == {"amendment": 7}
    assert [item.date for item in response.items] == [
        "2024-01-04",
        "2024-01-03",
        "2024-01-02",
    ]
    assert client.search.call_args.kwargs["body"]["from"] == 3
    assert client.search.call_args.kwargs["index"] == ["congress-amendment-read"]


@pytest.mark.parametrize(
    "types,page,limit",
    [
        ("nonsense", 1, 10),
        ("bill,nonsense", 1, 10),
        (None, 101, 100),
        (None, 0, 10),
        (None, 1, 101),
        ("x" * 201, 1, 10),
    ],
)
def test_invalid_activity_is_rejected_before_search(
    types: str | None, page: int, limit: int
) -> None:
    service, client = install([], {})
    with pytest.raises(QueryReadError):
        service.list_activity("A000001", types, page, limit)
    client.search.assert_not_called()


def test_activity_rejects_failed_shards_and_noncanonical_ids() -> None:
    service, _ = install([], {"bill": 0}, failed=1)
    with pytest.raises(IncompleteSearchError):
        service.list_activity("A000001", "bill", 1, 10)
    service, _ = install([{"id": "not-an-activity"}], {"bill": 1})
    with pytest.raises(IncompleteSearchError):
        service.list_activity("A000001", "bill", 1, 10)

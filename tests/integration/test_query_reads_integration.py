import json
import os
from collections.abc import Iterator
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest
from elastic_transport import ObjectApiResponse
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from cdm.backend.app import app
from cdm.backend.dependencies import get_container
from cdm.config import AppConfig
from cdm.container import Container
from cdm.store.opensearch import read_alias
from cdm.utils.json_types import JsonObject


class QueryFixture:
    resources = ("bill", "amendment", "rollcall", "house_vote", "member")

    def __init__(self, client: Elasticsearch) -> None:
        self.client = client
        self.indexes: list[str] = []
        self.responses: list[JsonObject] = []
        self.spy = Mock(spec=Elasticsearch)
        self.spy.search.side_effect = lambda **kwargs: self.record(
            client.search(**kwargs)
        )

    def record(
        self, response: ObjectApiResponse[JsonObject]
    ) -> ObjectApiResponse[JsonObject]:
        self.responses.append(response.body)
        return response

    def records(self) -> Iterator[JsonObject]:
        for number in range(1, 10002):
            for resource in ("bill", "amendment"):
                identity = (
                    f"{resource}:119:{'hr' if resource == 'bill' else 'hamdt'}:{number}"
                )
                yield {
                    "_index": read_alias(resource),
                    "_id": identity,
                    "_source": {
                        "id": identity,
                        **({"source_type": "bill"} if resource == "bill" else {}),
                        "congress": 119,
                        "title": f"Fixture {resource} {number}",
                        "update_date": "2026-01-01"
                        if resource == "bill"
                        else "2020-01-01",
                        **(
                            {"latest_action_date": "2026-01-01"}
                            if resource == "bill"
                            else {"submitted_date": "2020-01-01"}
                        ),
                        "sponsor_bioguide_ids": ["A000001"],
                        "full_text": "Excluded full text " * 30,
                    },
                }
        for number in range(1, 20002):
            congress = 119 if number <= 20000 else 120
            yield {
                "_index": read_alias("rollcall"),
                "_id": str(number),
                "_source": {
                    "id": str(number),
                    "congress": congress,
                    "legislation_id": f"bill:{congress}:hr:{number}",
                },
            }
        for number in range(1, 101):
            yield {
                "_index": read_alias("member"),
                "_id": f"member:A{number:06}",
                "_source": {
                    "id": f"member:A{number:06}",
                    "bioguide_id": f"A{number:06}",
                    "name": f"Fixture member {number}",
                },
            }
        for identity, source_type, dates in (
            (
                "bill:118:hr:1",
                "bill",
                {"latest_action_date": "2025-01-01", "update_date": "2027-01-01"},
            ),
            (
                "bill:118:hr:2",
                "bill",
                {"submitted_date": "2099-01-01", "update_date": "2024-01-01"},
            ),
            ("bill:118:hr:3", "bill", {}),
            ("law:118:1", "law", {"update_date": "2099-01-01"}),
            (
                "amendment:118:hamdt:1",
                "amendment",
                {"submitted_date": "2026-01-01", "latest_action_date": "2099-01-01"},
            ),
            (
                "amendment:118:hamdt:2",
                "amendment",
                {"update_date": "2023-01-01", "latest_action_date": "2099-01-01"},
            ),
        ):
            yield {
                "_index": read_alias(
                    "amendment" if source_type == "amendment" else "bill"
                ),
                "_id": identity,
                "_source": {
                    "id": identity,
                    "source_type": source_type,
                    "congress": 118,
                    "title": "Chronology",
                    "amended_bill": {
                        "id": "bill:118:hr:99",
                        "title": "Parent",
                        "full_text": "Excluded nested text",
                    },
                    "sponsor_bioguide_ids": ["A999999"],
                    **dates,
                },
            }

    def seed(self) -> None:
        for resource in self.resources:
            if self.client.indices.exists(index=read_alias(resource)):
                raise RuntimeError("Query tests require an empty isolated cluster")
        for resource in self.resources:
            index = f"query-read-test-{uuid4().hex}"
            self.client.indices.create(
                index=index,
                aliases={read_alias(resource): {}},
                settings={"number_of_shards": 1, "number_of_replicas": 0},
                mappings={
                    "dynamic": False,
                    "properties": {
                        **{
                            field: {"type": "keyword"}
                            for field in (
                                "id",
                                "source_type",
                                "sponsor_bioguide_ids",
                                "cosponsor_bioguide_ids",
                                "legislation_id",
                                "legislation_type",
                                "bioguide_id",
                                "state_code",
                            )
                        },
                        **{
                            field: {"type": "date"}
                            for field in (
                                "update_date",
                                "latest_action_date",
                                "submitted_date",
                            )
                        },
                        "congress": {"type": "integer"},
                        "legislation_number": {"type": "integer"},
                        "title": {"type": "text"},
                        "name": {"type": "text"},
                    },
                },
            )
            self.indexes.append(index)
        bulk(self.client, self.records(), chunk_size=500)
        self.client.indices.refresh(index=self.indexes)


@pytest.fixture(scope="module")
def fixture() -> Iterator[QueryFixture]:
    url = os.environ.get("QUERY_READS_TEST_URL")
    if not url:
        pytest.skip(
            "Set QUERY_READS_TEST_URL to an empty isolated Elasticsearch server"
        )
    client = Elasticsearch(url, request_timeout=90, max_retries=0)
    fixture = QueryFixture(client)
    try:
        fixture.seed()
        yield fixture
    finally:
        for index in fixture.indexes:
            client.indices.delete(index=index, ignore_unavailable=True)
        client.close()


@pytest.fixture
def container(fixture: QueryFixture, monkeypatch: pytest.MonkeyPatch) -> Container:
    fixture.spy.reset_mock()
    fixture.responses.clear()
    container = Container(AppConfig())
    container.__dict__["elastic_client"] = fixture.spy
    monkeypatch.setitem(app.dependency_overrides, get_container, lambda: container)
    return container


def test_real_activity_fetches_only_one_page_at_the_window_boundary(
    container: Container, fixture: QueryFixture
) -> None:
    result = container.member_service.list_activity("A000001", page=100, limit=100)
    assert result.total == 20002 and result.counts == {
        "bill": 10001,
        "amendment": 10001,
    }
    assert result.max_page == 100 and result.window_limited
    expected = sorted(f"bill:119:hr:{n}" for n in range(1, 10002))[9900:10000]
    assert [item.id for item in result.items] == expected
    fixture.spy.search.assert_called_once()
    request = fixture.spy.search.call_args.kwargs
    assert request["body"]["size"] == 100 and request["body"]["from"] == 9900
    assert "full_text" not in request["body"]["_source"]
    hits = fixture.responses[0]["hits"]
    assert isinstance(hits, dict)
    items = hits["hits"]
    assert isinstance(items, list) and len(items) == 100
    assert len(json.dumps(fixture.responses[0], separators=(",", ":")).encode()) < 50000
    assert (
        container.member_service.list_activity("A000001", page=100, limit=100) == result
    )


def test_displayed_dates_fallbacks_missing_dates_and_source_filter_match_sort(
    container: Container,
) -> None:
    result = container.member_service.list_activity("A999999")
    assert result.total == 5 and result.counts == {"bill": 3, "amendment": 2}
    assert [item.id for item in result.items] == [
        "amendment:118:hamdt:1",
        "bill:118:hr:1",
        "bill:118:hr:2",
        "amendment:118:hamdt:2",
        "bill:118:hr:3",
    ]
    assert [item.date for item in result.items] == [
        "2026-01-01",
        "2025-01-01",
        "2024-01-01",
        "2023-01-01",
        None,
    ]
    selected = container.member_service.list_activity("A999999", "amendment,amendment")
    assert selected.total == 2 and selected.counts == {"amendment": 2}
    assert selected.items[1].title.endswith("to Parent")
    assert selected.items[1].bill_id == "bill:118:hr:99"


def test_real_grouped_search_returns_each_requested_group_and_stable_ties(
    container: Container,
) -> None:
    result = container.search_service.search("Fixture", "member,bill", 100)
    assert len(result.results) == 200 and result.ordering == "grouped"
    assert [item.result_type for item in result.results] == ["member"] * 100 + [
        "bill"
    ] * 100
    assert [item.id for item in result.results[:100]] == [
        f"A{n:06}" for n in range(1, 101)
    ]
    assert result == container.search_service.search("Fixture", "member,bill", 100)


def test_vote_scope_at_twenty_thousand_ids_is_complete(container: Container) -> None:
    result = container.bill_service.list_recent(congress=119, has_votes=True)
    assert result.total == 10001 and len(result.bills) == 50 and result.window_limited
    assert all(bill.vote_count == 1 for bill in result.bills)


@pytest.mark.asyncio
async def test_real_http_rejects_unsupported_scope_and_depth_before_partial_success(
    container: Container,
    fixture: QueryFixture,
) -> None:
    before = {
        resource: fixture.client.count(index=read_alias(resource))["count"]
        for resource in fixture.resources
    }
    source = fixture.client.get(index=read_alias("bill"), id="bill:119:hr:1").body
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://fixture"
    ) as api:
        for path in (
            "/api/v1/bills/recent?page=101&limit=100",
            "/api/v1/members?page=101&limit=100",
            "/api/v1/members/A000001/activity?page=101&limit=100",
        ):
            fixture.spy.reset_mock()
            rejected = await api.get(path)
            assert rejected.status_code == 422 and rejected.json()["detail"][0][
                "loc"
            ] == ["query", "page"]
            fixture.spy.search.assert_not_called()
        oversized = await api.get("/api/v1/bills/recent?has_votes=true")
        assert oversized.status_code == 422
        assert oversized.json()["detail"][0]["loc"] == ["query", "has_votes"]
        allowed = await api.get("/api/v1/bills/recent?has_votes=true&congress=119")
        assert allowed.status_code == 200 and allowed.json()["total"] == 10001
        members = await api.get("/api/v1/members")
        assert members.status_code == 200 and members.json()["max_page"] == 2
    assert (
        fixture.client.get(index=read_alias("bill"), id="bill:119:hr:1").body == source
    )
    assert {
        resource: fixture.client.count(index=read_alias(resource))["count"]
        for resource in fixture.resources
    } == before

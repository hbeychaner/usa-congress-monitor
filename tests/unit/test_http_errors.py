import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock

import httpx
import pytest
from elastic_transport import (
    ApiResponseMeta,
    ConnectionError,
    HttpHeaders,
    NodeConfig,
    ObjectApiResponse,
)
from elasticsearch import ApiError, Elasticsearch, NotFoundError

from cdm.backend.app import app
from cdm.backend.dependencies import (
    get_bill_service,
    get_container,
    get_member_service,
    get_search_service,
)
from cdm.backend.services.bill_service import BillService
from cdm.backend.services.bill_vote_index import BillVoteIndex
from cdm.backend.services.member_service import MemberService
from cdm.backend.services.search_service import SearchService
from cdm.backend.services.state_service import StateService
from cdm.config import ApiConfig
from cdm.container import Container
from cdm.contracts.api import StateSummary
from cdm.store.client import SearchConfigurationError
from cdm.utils.json_types import JsonObject


def meta(status: int = 200) -> ApiResponseMeta:
    return ApiResponseMeta(
        status, "1.1", HttpHeaders(), 0, NodeConfig("http", "localhost", 9200)
    )


def search_response(
    hits: list[JsonObject] | None = None, *, timed_out: bool = False, failed: int = 0
) -> ObjectApiResponse[JsonObject]:
    return ObjectApiResponse(
        {
            "timed_out": timed_out,
            "_shards": {"failed": failed},
            "hits": {"hits": hits or []},
        },
        meta(),
    )


async def get(path: str) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://fixture",
    ) as client:
        return await client.get(path)


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["document", "wrong_type", "index"])
async def test_bill_missing_document_is_404_but_missing_index_is_503(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    client = Mock(spec=Elasticsearch)
    if missing == "wrong_type":
        client.get.return_value = {"_source": {"source_type": "amendment"}}
    else:
        client.get.side_effect = NotFoundError(
            "not found",
            meta(404),
            {"found": False}
            if missing == "document"
            else {"error": {"type": "index_not_found_exception"}},
        )
    service = BillService(client, Mock(spec=BillVoteIndex))
    monkeypatch.setitem(app.dependency_overrides, get_bill_service, lambda: service)
    response = await get("/api/v1/bills/bill:119:hr:1")
    assert response.status_code == (503 if missing == "index" else 404)
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_missing_member_uses_the_same_missing_entity_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock(spec=Elasticsearch)
    client.search.return_value = search_response()
    service = MemberService(client, Mock(spec=SearchService))
    monkeypatch.setitem(app.dependency_overrides, get_member_service, lambda: service)
    response = await get("/api/v1/members/UNKNOWN")
    assert response.status_code == 404
    assert response.json() == {"detail": "Member not found: UNKNOWN"}


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["state", "member", "bill"])
async def test_any_requested_search_source_failure_rejects_all_partial_results(
    monkeypatch: pytest.MonkeyPatch, source: str, caplog: pytest.LogCaptureFixture
) -> None:
    client = Mock(spec=Elasticsearch)
    states = Mock(spec=StateService)
    states.list_states.return_value = [StateSummary(code="CA", name="California")]
    failure = ConnectionError("private credentials must not escape")
    if source == "state":
        states.list_states.side_effect = failure
    elif source == "member":
        client.search.side_effect = failure
    else:
        client.search.side_effect = [search_response(), failure]
    service = SearchService(client, states)
    monkeypatch.setitem(app.dependency_overrides, get_search_service, lambda: service)
    response = await get("/api/v1/search?q=California")
    assert response.status_code == 503
    assert response.json() == {
        "detail": "Search service unavailable; please try again later.",
        "analysis_state": "unavailable",
    }
    assert "results" not in response.json()
    assert "private credentials" not in response.text + caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("partial", ["timeout", "shards"])
@pytest.mark.parametrize("source", ["member", "bill", "state"])
async def test_incomplete_search_responses_are_not_reported_as_empty_success(
    monkeypatch: pytest.MonkeyPatch, partial: str, source: str
) -> None:
    client = Mock(spec=Elasticsearch)
    client.search.return_value = search_response(
        timed_out=partial == "timeout", failed=int(partial == "shards")
    )
    service = SearchService(client, StateService(client))
    monkeypatch.setitem(app.dependency_overrides, get_search_service, lambda: service)
    response = await get(f"/api/v1/search?q=none&types={source}")
    assert response.status_code == 503
    assert client.search.call_args.kwargs["allow_partial_search_results"] is False


@pytest.mark.asyncio
async def test_empty_search_is_success_and_invalid_input_is_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock(spec=Elasticsearch)
    client.search.return_value = search_response()
    states = Mock(spec=StateService)
    service = SearchService(client, states)
    monkeypatch.setitem(app.dependency_overrides, get_search_service, lambda: service)
    empty = await get("/api/v1/search?q=absent&types=bill")
    assert empty.status_code == 200 and empty.json()["results"] == []
    invalid = await get("/api/v1/search?q=absent&limit=0")
    assert invalid.status_code == 422
    states.list_states.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["/api/v1/bills/recent", "/api/v1/members/A"])
async def test_partial_primary_queries_cannot_look_empty_or_missing(
    monkeypatch: pytest.MonkeyPatch, route: str
) -> None:
    client = Mock(spec=Elasticsearch)
    client.search.return_value = search_response(timed_out=True)
    bills = BillService(client, Mock(spec=BillVoteIndex))
    members = MemberService(client, Mock(spec=SearchService))
    monkeypatch.setitem(app.dependency_overrides, get_bill_service, lambda: bills)
    monkeypatch.setitem(app.dependency_overrides, get_member_service, lambda: members)
    response = await get(route)
    assert response.status_code == 503
    assert client.search.call_args.kwargs["allow_partial_search_results"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/v1/search?q=test", "/api/v1/members/A"])
async def test_programming_errors_are_not_disguised_as_404_or_partial_results(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    service = Mock()
    service.search.side_effect = ValueError("private internal bug")
    service.get_profile.side_effect = ValueError("private internal bug")
    monkeypatch.setitem(app.dependency_overrides, get_search_service, lambda: service)
    monkeypatch.setitem(app.dependency_overrides, get_member_service, lambda: service)
    response = await get(path)
    assert response.status_code == 500
    assert "private internal bug" not in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 404, 429, 503])
async def test_search_backend_errors_do_not_leak_details(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, status: int
) -> None:
    client = Mock(spec=Elasticsearch)
    client.options.return_value.info.side_effect = ApiError(
        "private endpoint and credentials",
        meta(status),
        {"error": "private backend body"},
    )
    container = Mock(
        spec=Container, elastic_client=client, config=Mock(api=ApiConfig())
    )
    monkeypatch.setitem(app.dependency_overrides, get_container, lambda: container)
    response = await get("/ready")
    assert response.status_code == 503
    assert "private" not in response.text + caplog.text


@pytest.mark.asyncio
async def test_readiness_checks_only_the_dependency_with_a_bounded_no_retry_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock(spec=Elasticsearch)
    container = Mock(
        spec=Container,
        elastic_client=client,
        config=Mock(api=ApiConfig(readiness_timeout_secs=0.1)),
    )
    monkeypatch.setitem(app.dependency_overrides, get_container, lambda: container)
    response = await get("/ready")
    assert response.status_code == 200 and response.json() == {"status": "ready"}
    client.options.assert_called_once_with(
        request_timeout=0.1, max_retries=0, retry_on_timeout=False
    )
    client.options.return_value.info.assert_called_once_with()
    client.search.assert_not_called()
    container.analytics_jobs.assert_not_called()


@pytest.mark.asyncio
async def test_liveness_remains_cheap_when_container_or_dependencies_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unavailable = Mock(side_effect=SearchConfigurationError("private configuration"))

    def failed_container() -> Container:
        return unavailable()

    monkeypatch.setitem(app.dependency_overrides, get_container, failed_container)
    response = await get("/health")
    assert response.status_code == 200 and response.json() == {"status": "ok"}
    unavailable.assert_not_called()
    assert (await get("/ready")).status_code == 503


class StalledServer(ThreadingHTTPServer):
    attempts: int = 0

    def __init__(self) -> None:
        self.release = threading.Event()
        super().__init__(("127.0.0.1", 0), StalledHandler)


class StalledHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if not isinstance(self.server, StalledServer):
            raise TypeError("Expected owned test server")
        self.server.attempts += 1
        self.server.release.wait(timeout=3)


@pytest.mark.asyncio
async def test_actual_stalled_dependency_times_out_without_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = StalledServer()
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}
    )
    thread.start()
    client = Elasticsearch(f"http://127.0.0.1:{server.server_port}")
    container = Mock(
        spec=Container,
        elastic_client=client,
        config=Mock(api=ApiConfig(readiness_timeout_secs=0.1)),
    )
    monkeypatch.setitem(app.dependency_overrides, get_container, lambda: container)
    try:
        started = time.monotonic()
        response = await get("/ready")
        elapsed = time.monotonic() - started
        assert response.status_code == 503
        assert elapsed < 1.0
        assert server.attempts == 1
    finally:
        server.release.set()
        client.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert not thread.is_alive()

from datetime import UTC, datetime
from unittest.mock import Mock

import httpx
import pytest
from elastic_transport import (
    ApiResponseMeta,
    HttpHeaders,
    NodeConfig,
    ObjectApiResponse,
)
from elasticsearch import Elasticsearch, NotFoundError

from cdm.backend.app import app
from cdm.backend.dependencies import (
    get_member_service,
    get_party_service,
    get_topic_service,
)
from cdm.backend.services.graph_service import GraphReadSnapshot, GraphService
from cdm.backend.services.member_metasubject_overlay import (
    MemberMetasubjectOverlayBuilder,
)
from cdm.backend.services.member_service import MemberService
from cdm.backend.services.member_topic_overlay import MemberTopicOverlayBuilder
from cdm.backend.services.neighborhood_service import (
    NeighborhoodQuery,
    NeighborhoodService,
)
from cdm.backend.services.party_service import PartyService
from cdm.backend.services.search_service import SearchService
from cdm.backend.services.similar_bill_service import SimilarBillService
from cdm.backend.services.sponsored_bills import SponsoredBillReader
from cdm.backend.services.subject_service import SubjectService
from cdm.backend.services.topic_service import TopicService
from cdm.config import PerspectiveConfig
from cdm.contracts.analysis import AnalysisState, AnalysisStatus
from cdm.contracts.api import MemberSummary, MetasubjectSummary, TopicSummary
from cdm.graph.models import GraphVersionPointer, MemberEdge, Signal
from cdm.graph.store import GraphStore
from cdm.perspectives.models import TopicPerspectives
from cdm.store.client import IncompleteSearchError
from cdm.store.embedding_store import EmbeddingNeighbors, EmbeddingStore
from cdm.store.opensearch import read_alias
from cdm.store.perspective_repository import PerspectiveRepository
from cdm.store.topic_publication import (
    CompletedTopicRun,
    TopicPublicationStore,
    TopicRunCounts,
)
from cdm.utils.json_types import JsonObject


def meta(status: int = 200) -> ApiResponseMeta:
    return ApiResponseMeta(
        status, "1.1", HttpHeaders(), 0, NodeConfig("http", "localhost", 9200)
    )


def run(version: str = "v1") -> CompletedTopicRun:
    return CompletedTopicRun(
        model_version=version,
        trained_at=datetime(2026, 1, 1, tzinfo=UTC),
        completed_at=datetime(2026, 1, 1, tzinfo=UTC),
        embedding_model="encoder",
        min_congress=113,
        corpus_size=1,
        dated_documents=0,
        model_path="models/test",
        counts=TopicRunCounts(
            topics=1,
            assignments=1,
            over_time=0,
            metasubjects=1,
            metasubject_over_time=0,
        ),
    )


def response(
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


def service(client: Mock, published: bool = True) -> TopicService:
    publications = Mock(spec=TopicPublicationStore)
    publications.current.return_value = run() if published else None
    subjects = Mock(spec=SubjectService)
    subjects.member_subject_items.return_value = ([], [])
    return TopicService(client, "analysis", subjects, publications)


async def get(path: str) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://fixture",
    ) as client:
        return await client.get(path)


@pytest.mark.asyncio
async def test_lost_published_index_is_not_a_successful_empty_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock(spec=Elasticsearch)
    client.search.side_effect = NotFoundError(
        "missing", meta(404), {"error": {"type": "index_not_found_exception"}}
    )
    topics = service(client)
    monkeypatch.setitem(app.dependency_overrides, get_topic_service, lambda: topics)
    result = await get("/api/v1/topics")
    assert result.status_code == 503
    assert result.json()["analysis_state"] == "unavailable"


@pytest.mark.asyncio
async def test_unbuilt_topic_detail_is_not_an_unknown_topic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    topics = service(Mock(spec=Elasticsearch), published=False)
    monkeypatch.setitem(app.dependency_overrides, get_topic_service, lambda: topics)
    result = await get("/api/v1/topics/1")
    assert result.status_code == 503
    assert result.json()["analysis_state"] == "not_built"


@pytest.mark.parametrize(
    ("source", "published", "has_results", "state"),
    [
        (None, None, False, AnalysisState.NOT_BUILT),
        (None, "v2", False, AnalysisState.NOT_BUILT),
        ("v1", "v1", True, AnalysisState.AVAILABLE),
        ("v1", "v1", False, AnalysisState.EMPTY),
        ("v1", "v2", True, AnalysisState.STALE),
        ("v1", "v2", False, AnalysisState.STALE),
        ("legacy", None, True, AnalysisState.UNKNOWN),
    ],
)
def test_model_status_uses_identity_not_timestamps(
    source: str | None, published: str | None, has_results: bool, state: AnalysisState
) -> None:
    status = AnalysisStatus.for_model(source, published, has_results)
    assert status.state is state
    assert status.source_model_version == source
    assert status.published_model_version == published


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/topics",
        "/api/v1/topics/trends",
        "/api/v1/topics/metasubjects",
        "/api/v1/topics/metasubjects/trends",
        "/api/v1/members/A/topics",
        "/api/v1/bills/bill:119:hr:1/topics",
    ],
)
async def test_unbuilt_lists_are_explicit_without_querying_analysis(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    client = Mock(spec=Elasticsearch)
    topics = service(client, published=False)
    monkeypatch.setitem(app.dependency_overrides, get_topic_service, lambda: topics)
    result = await get(path)
    assert result.status_code == 200
    assert result.json()["analysis"]["state"] == "not_built"
    client.search.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_topic_in_a_published_model_remains_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock(spec=Elasticsearch)
    client.search.return_value = response([{"_source": {"topic_id": 1, "size": 1}}])
    topics = service(client)
    monkeypatch.setitem(app.dependency_overrides, get_topic_service, lambda: topics)
    result = await get("/api/v1/topics/99")
    assert result.status_code == 404
    assert result.json() == {"detail": "topic not found"}


def test_published_outlier_only_model_and_missing_dates_are_built_empty() -> None:
    client = Mock(spec=Elasticsearch)
    client.search.return_value = response([{"_source": {"topic_id": -1, "size": 1}}])
    assert service(client).list_topics().analysis.state is AnalysisState.EMPTY
    client.search.side_effect = [
        response([{"_source": {"topic_id": 1, "size": 1}}]),
        response(),
    ]
    assert service(client).list_topic_trends().analysis.state is AnalysisState.EMPTY


@pytest.mark.parametrize("method", ["list_topics", "list_metasubjects"])
def test_published_summary_loss_cannot_masquerade_as_empty(method: str) -> None:
    client = Mock(spec=Elasticsearch)
    client.search.return_value = response()
    topics = service(client)
    with pytest.raises(IncompleteSearchError):
        if method == "list_topics":
            topics.list_topics()
        else:
            topics.list_metasubjects()


@pytest.mark.parametrize("kind", ["topics", "graph", "perspectives", "similarity"])
@pytest.mark.parametrize("timed_out", [True, False])
def test_partial_analytics_queries_are_rejected(kind: str, timed_out: bool) -> None:
    client = Mock(spec=Elasticsearch)
    client.search.return_value = response(
        timed_out=timed_out, failed=0 if timed_out else 1
    )
    with pytest.raises(IncompleteSearchError):
        match kind:
            case "topics":
                service(client).list_topics()
            case "graph":
                GraphService(
                    GraphStore(client),
                    Mock(spec=MemberService),
                    Mock(spec=TopicPublicationStore),
                ).edges("graph", Signal.TOPIC, ["A"], None, 5)
            case "perspectives":
                PerspectiveRepository(client, "analysis").congresses()
            case "similarity":
                client.get.return_value = {
                    "_source": {"model": "encoder", "embedding": [1.0, 0.0]}
                }
                EmbeddingStore(client, "encoder", index="cache", batch_docs=2).similar(
                    "bill", 5
                )


@pytest.mark.asyncio
async def test_core_profile_never_requests_optional_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock(spec=Elasticsearch)
    client.search.side_effect = [
        response(
            [
                {
                    "_source": {
                        "bioguide_id": "A",
                        "name": "Member A",
                        "state": "CA",
                        "party": "Democratic",
                    }
                }
            ]
        ),
        response(),
    ]
    members = MemberService(client, Mock(spec=SearchService))
    monkeypatch.setitem(app.dependency_overrides, get_member_service, lambda: members)
    result = await get("/api/v1/members/A")
    assert result.status_code == 200
    assert result.json()["member"]["bioguide_id"] == "A"
    assert "topics" not in result.json()
    assert [call.kwargs["index"] for call in client.search.call_args_list] == [
        read_alias("member"),
        read_alias("bill"),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source", "published", "results", "state"),
    [
        ("v1", "v1", True, "available"),
        ("v1", "v1", False, "empty"),
        ("v1", "v2", True, "stale"),
        ("legacy", None, True, "unknown"),
        (None, "v1", False, "not_built"),
    ],
)
async def test_party_states_preserve_snapshot_results(
    monkeypatch: pytest.MonkeyPatch,
    source: str | None,
    published: str | None,
    results: bool,
    state: str,
) -> None:
    repository = Mock(spec=PerspectiveRepository)
    repository.congresses.return_value = [119]
    repository.read.return_value = (
        [TopicPerspectives(congress=119, topic_id=1, topic_label="Health", bills=1)]
        if results
        else [],
        source,
    )
    publications = Mock(spec=TopicPublicationStore)
    publications.current.return_value = run(published) if published else None
    parties = PartyService(repository, PerspectiveConfig(), publications)
    monkeypatch.setitem(app.dependency_overrides, get_party_service, lambda: parties)
    result = await get("/api/v1/parties?congress=119")
    assert result.status_code == 200
    assert result.json()["analysis"]["state"] == state
    assert result.json()["model_version"] == source
    if results:
        detail = await get("/api/v1/parties/topics/1?congress=119")
        assert detail.status_code == 200
        assert detail.json()["topic"]["topic_label"] == "Health"
        assert detail.json()["analysis"]["state"] == state


@pytest.mark.parametrize(
    ("source", "congresses", "congress", "has_results", "state"),
    [
        ("v1", [119], 119, True, AnalysisState.AVAILABLE),
        ("v1", [119], 119, False, AnalysisState.EMPTY),
        ("v1", [119], 118, False, AnalysisState.NOT_BUILT),
        ("old", [119], 119, True, AnalysisState.STALE),
        ("old", [119], 119, False, AnalysisState.STALE),
        (None, None, 119, True, AnalysisState.UNKNOWN),
        ("v1", None, 119, False, AnalysisState.UNKNOWN),
        ("v1", None, None, False, AnalysisState.UNKNOWN),
    ],
)
def test_graph_status_uses_pinned_lineage_and_congress_scope(
    source: str | None,
    congresses: list[int] | None,
    congress: int | None,
    has_results: bool,
    state: AnalysisState,
) -> None:
    snapshot = GraphReadSnapshot(
        pointers={
            Signal.TOPIC: GraphVersionPointer(
                signal=Signal.TOPIC,
                graph_version="graph",
                source_model_version=source,
                congresses=congresses,
            )
        },
        topic_model_version="v1",
    )
    assert (
        snapshot.analysis({Signal.TOPIC} if has_results else set(), congress)[
            Signal.TOPIC
        ].state
        is state
    )


def test_missing_selected_signal_is_visible_without_requiring_topic_dependencies() -> (
    None
):
    client = Mock(spec=Elasticsearch)
    pointer = GraphVersionPointer(
        signal=Signal.COLLABORATION, graph_version="graph", congresses=[119]
    )
    client.get.side_effect = [
        {"_source": pointer.model_dump(mode="json")},
        NotFoundError("missing", meta(404), {"found": False}),
    ]
    edge = MemberEdge(
        graph_version="graph",
        signal=Signal.COLLABORATION,
        member="A",
        neighbor="B",
        score=1.0,
    )
    client.search.return_value = response([{"_source": edge.model_dump(mode="json")}])
    publications = Mock(spec=TopicPublicationStore)
    publications.current.side_effect = AssertionError("unrelated topic dependency")
    members = Mock(spec=MemberService)
    members.get_summaries.return_value = {
        member: MemberSummary(
            bioguide_id=member, display_name=member, party="Democratic", state="CA"
        )
        for member in ("A", "B")
    }
    graph = GraphService(GraphStore(client), members, publications)
    neighborhoods = NeighborhoodService(graph, members, Mock(), Mock(), Mock())
    result = neighborhoods.neighborhood(
        NeighborhoodQuery(
            seeds=["A"], weights={Signal.COLLABORATION: 1.0, Signal.VOTING: 1.0}
        )
    )
    assert result.links
    assert result.analysis[Signal.COLLABORATION].state is AnalysisState.AVAILABLE
    assert result.analysis[Signal.VOTING].state is AnalysisState.NOT_BUILT
    assert client.get.call_count == 2
    publications.current.assert_not_called()


@pytest.mark.parametrize("found", [True, False])
def test_missing_legacy_cache_is_not_confused_with_an_empty_neighbor_query(
    found: bool,
) -> None:
    client = Mock(spec=Elasticsearch, indices=Mock())
    client.indices.exists.return_value = found
    store = Mock(spec=EmbeddingStore, index="legacy")
    store.similar.return_value = EmbeddingNeighbors(source_found=True, neighbors=[])
    publications = Mock(spec=TopicPublicationStore)
    publications.current.return_value = None
    result = SimilarBillService(client, store, publications).similar("bill", 5)
    assert result.analysis.state is (
        AnalysisState.UNKNOWN if found else AnalysisState.NOT_BUILT
    )
    assert store.similar.call_count == int(found)


@pytest.mark.parametrize("missing", ["document", "index"])
def test_missing_embedding_document_is_distinct_from_a_lost_index(
    missing: str,
) -> None:
    client = Mock(spec=Elasticsearch)
    client.get.side_effect = NotFoundError(
        "missing",
        meta(404),
        {"found": False}
        if missing == "document"
        else {"error": {"type": "index_not_found_exception"}},
    )
    store = EmbeddingStore(client, "encoder", index="cache", batch_docs=2)
    if missing == "document":
        assert store.similar("bill", 5) == EmbeddingNeighbors(
            source_found=False, neighbors=[]
        )
    else:
        with pytest.raises(NotFoundError):
            store.similar("bill", 5)


@pytest.mark.parametrize("kind", ["topic", "metasubject"])
@pytest.mark.parametrize("version", ["pinned", None])
def test_overlays_use_the_response_publication_without_resolving_it_again(
    kind: str,
    version: str | None,
) -> None:
    topics = Mock(spec=TopicService)
    topics.latest_model_version.side_effect = AssertionError("publication changed")
    topics.member_assignments.return_value = [("b1", 1), ("b2", 1)]
    topics.member_metasubject_assignments.return_value = [("b1", 1), ("b2", 1)]
    topics.topic_summaries.return_value = {
        1: TopicSummary(topic_id=1, name="Health", label="Health", size=2)
    }
    topics.metasubject_summaries.return_value = {
        1: MetasubjectSummary(metasubject_id=1, name="Health", size=2)
    }
    bills = Mock(spec=SponsoredBillReader)
    bills.by_member.return_value = {"A": ["b1", "b2"]}
    builder = (
        MemberTopicOverlayBuilder(bills, topics)
        if kind == "topic"
        else MemberMetasubjectOverlayBuilder(bills, topics)
    )
    overlay = builder.build(["A"], 119, 3, version)
    assert len(overlay.links) == (1 if version else 0)
    topics.latest_model_version.assert_not_called()
    if version is None:
        bills.by_member.assert_not_called()
    else:
        reader = (
            topics.member_assignments
            if kind == "topic"
            else topics.member_metasubject_assignments
        )
        reader.assert_called_once_with(["b1", "b2"], "pinned")

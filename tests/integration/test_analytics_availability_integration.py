import os
from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest
from elasticsearch import Elasticsearch

from cdm.backend.app import app
from cdm.backend.dependencies import (
    get_graph_service,
    get_party_service,
    get_similar_bill_service,
    get_topic_service,
)
from cdm.backend.services.graph_service import GraphService
from cdm.backend.services.member_service import MemberService
from cdm.backend.services.party_service import PartyService
from cdm.backend.services.similar_bill_service import SimilarBillService
from cdm.backend.services.subject_service import SubjectService
from cdm.backend.services.topic_service import TopicService
from cdm.config import PerspectiveConfig
from cdm.config.topic_analysis import EmbeddingCache, GraphStoreConfig, TopicKind
from cdm.contracts.api import MemberSummary
from cdm.contracts.labels import LabelFallbackReason, LabelProvenance, LabelSource
from cdm.graph.models import GraphVersionPointer, MemberEdge, Signal
from cdm.graph.store import GraphStore
from cdm.perspectives.models import Perspective, TopicPerspectives
from cdm.store.embedding_store import EmbeddingRecord, EmbeddingStore
from cdm.store.index_manager import load_definitions
from cdm.store.perspective_repository import PerspectiveRepository
from cdm.store.topic_publication import (
    TopicPublicationStore,
    TopicRunCounts,
    TopicRunSpecification,
)
from cdm.utils.json_types import JsonObject


@pytest.fixture
def client() -> Iterator[Elasticsearch]:
    url = os.environ.get("ANALYTICS_AVAILABILITY_TEST_URL")
    if not url:
        pytest.skip("Set ANALYTICS_AVAILABILITY_TEST_URL to isolated Elasticsearch")
    with Elasticsearch(url, request_timeout=30, max_retries=0) as client:
        yield client


@pytest.fixture(autouse=True)
def source_guard(client: Elasticsearch) -> Iterator[None]:
    index = f"availability-source-{uuid4().hex}"
    source: JsonObject = {
        "id": "bill:119:hr:1",
        "title": "Preserved congressional record",
    }
    client.index(index=index, id="bill", document=source, refresh=True)
    try:
        yield
        assert client.get(index=index, id="bill")["_source"] == source
        assert client.count(index=index)["count"] == 1
    finally:
        client.indices.delete(index=index, ignore_unavailable=True)


@pytest.fixture
def publications(client: Elasticsearch) -> Iterator[TopicPublicationStore]:
    store = TopicPublicationStore(client, f"availability-analysis-{uuid4().hex}")
    try:
        yield store
    finally:
        client.indices.delete(index=store.index, ignore_unavailable=True)


@pytest.fixture
def embeddings(client: Elasticsearch) -> Iterator[EmbeddingStore]:
    store = EmbeddingStore(
        client, "encoder", index=f"availability-cache-{uuid4().hex}", batch_docs=2
    )
    try:
        yield store
    finally:
        client.indices.delete(index=store.index, ignore_unavailable=True)


def publish(
    store: TopicPublicationStore,
    version: str,
    cache: EmbeddingCache | None = None,
    provenance: LabelProvenance | None = None,
) -> None:
    expected = store.snapshot()
    specification = TopicRunSpecification(
        model_version=version,
        trained_at=datetime.now(UTC),
        embedding_model="encoder",
        embedding_cache=cache,
        min_congress=113,
        corpus_size=1,
        dated_documents=0,
        model_path=f"models/fixture-{version}",
        counts=TopicRunCounts(
            topics=1,
            assignments=1,
            over_time=0,
            metasubjects=1,
            metasubject_over_time=0,
        ),
    )
    outputs: dict[TopicKind, JsonObject] = {
        TopicKind.TOPIC: {"topic_id": 1, "name": "Health", "size": 1},
        TopicKind.ASSIGNMENT: {"topic_id": 1, "doc_id": "bill", "probability": 1.0},
        TopicKind.METASUBJECT: {
            "metasubject_id": 1,
            "name": "Health",
            "size": 1,
            "topic_ids": [1],
        },
    }
    if provenance is not None:
        for kind in (TopicKind.TOPIC, TopicKind.METASUBJECT):
            outputs[kind].update(provenance.model_dump(mode="json"))
    store.write(
        specification,
        [
            {
                "_index": store.index,
                "_id": f"{kind}:{version}:1",
                "_source": {"kind": kind, "model_version": version, **source},
            }
            for kind, source in outputs.items()
        ],
    )
    store.publish(version, expected)


async def get(path: str) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://fixture",
    ) as client:
        return await client.get(path)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provenance",
    [
        None,
        LabelProvenance(label_source=LabelSource.LLM),
        LabelProvenance(
            label_source=LabelSource.KEYWORDS,
            fallback_reason=LabelFallbackReason.REQUEST_FAILED,
        ),
    ],
)
async def test_label_provenance_round_trips_through_real_indexes_and_http(
    client: Elasticsearch,
    publications: TopicPublicationStore,
    monkeypatch: pytest.MonkeyPatch,
    provenance: LabelProvenance | None,
) -> None:
    publish(publications, "v1", provenance=provenance)
    origin = provenance or LabelProvenance()
    expected = origin.model_dump(mode="json")
    topics = TopicService(
        client, publications.index, Mock(spec=SubjectService), publications
    )
    monkeypatch.setitem(app.dependency_overrides, get_topic_service, lambda: topics)
    for path, key in (
        ("/api/v1/topics", "topics"),
        ("/api/v1/topics/metasubjects", "metasubjects"),
    ):
        response = await get(path)
        assert response.status_code == 200
        summary = response.json()[key][0]
        assert {field: summary[field] for field in expected} == expected

    perspective = Perspective(
        congress=119,
        topic_id=1,
        perspective_id=0,
        label="Health",
        size=1,
        label_source=origin.label_source,
        fallback_reason=origin.fallback_reason,
    )
    repository = PerspectiveRepository(client, publications.index)
    stored = TopicPerspectives(
        congress=119,
        topic_id=1,
        topic_label="Health",
        bills=1,
        passed=True,
        perspectives=[perspective],
    )
    repository.replace(119, "v1", datetime.now(UTC), [stored])
    parties = PartyService(repository, PerspectiveConfig(), publications)
    monkeypatch.setitem(app.dependency_overrides, get_party_service, lambda: parties)
    response = await get("/api/v1/parties/topics/1?congress=119")
    assert response.status_code == 200
    cluster = response.json()["topic"]["perspectives"][0]
    assert {field: cluster[field] for field in expected} == expected
    assert repository.read(119) == ([stored], "v1")


@pytest.mark.asyncio
async def test_real_publication_distinguishes_unbuilt_empty_and_lost_outputs(
    client: Elasticsearch,
    publications: TopicPublicationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    topics = TopicService(
        client, publications.index, Mock(spec=SubjectService), publications
    )
    monkeypatch.setitem(app.dependency_overrides, get_topic_service, lambda: topics)
    assert (await get("/api/v1/topics")).json()["analysis"]["state"] == "not_built"
    detail = await get("/api/v1/topics/1")
    assert detail.status_code == 503
    assert detail.json()["analysis_state"] == "not_built"
    publish(publications, "v1")
    assert (await get("/api/v1/topics")).json()["analysis"]["state"] == "available"
    assert (await get("/api/v1/topics/trends")).json()["analysis"]["state"] == "empty"
    client.delete(index=publications.index, id="topic:v1:1", refresh=True)
    lost = await get("/api/v1/topics")
    assert lost.status_code == 503
    assert lost.json()["analysis_state"] == "unavailable"
    assert publications.current() is not None


@pytest.mark.asyncio
async def test_real_perspective_snapshot_is_empty_or_stale_without_losing_results(
    client: Elasticsearch,
    publications: TopicPublicationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publish(publications, "v1")
    repository = PerspectiveRepository(client, publications.index)
    repository.replace(119, "v1", datetime.now(UTC), [])
    parties = PartyService(repository, PerspectiveConfig(), publications)
    monkeypatch.setitem(app.dependency_overrides, get_party_service, lambda: parties)
    assert (await get("/api/v1/parties")).json()["analysis"]["state"] == "empty"
    stored = TopicPerspectives(
        congress=119, topic_id=1, topic_label="Original topic", bills=1
    )
    repository.replace(119, "v1", datetime.now(UTC), [stored])
    publish(publications, "v2")
    overview = await get("/api/v1/parties")
    assert overview.json()["analysis"] == {
        "state": "stale",
        "source_model_version": "v1",
        "published_model_version": "v2",
    }
    detail = await get("/api/v1/parties/topics/1?congress=119")
    assert detail.json()["topic"]["topic_label"] == "Original topic"
    assert detail.json()["analysis"]["state"] == "stale"
    assert repository.read(119) == ([stored], "v1")


@pytest.mark.asyncio
async def test_real_empty_knn_is_distinct_from_a_missing_cache(
    client: Elasticsearch,
    publications: TopicPublicationStore,
    embeddings: EmbeddingStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SimilarBillService(client, embeddings, publications)
    monkeypatch.setitem(
        app.dependency_overrides, get_similar_bill_service, lambda: service
    )
    path = "/api/v1/bills/bill/similar"
    assert (await get(path)).json()["analysis"]["state"] == "not_built"
    embeddings.ensure_index(2)
    client.index(
        index=embeddings.index,
        id="bill",
        document=EmbeddingRecord(
            doc_id="bill", model="encoder", content_hash="fixture", embedding=[1.0, 0.0]
        ).model_dump(mode="json"),
        refresh=True,
    )
    cache = EmbeddingCache(index=embeddings.index, model="encoder", dimensions=2)
    publish(publications, "v1", cache)
    empty = await get(path)
    assert empty.status_code == 200
    assert empty.json()["analysis"]["state"] == "empty"
    missing_vector = await get("/api/v1/bills/new-bill/similar")
    assert missing_vector.status_code == 200
    assert missing_vector.json()["analysis"]["state"] == "not_built"
    client.indices.delete(index=embeddings.index)
    unavailable = await get(path)
    assert unavailable.status_code == 503
    assert unavailable.json()["analysis_state"] == "unavailable"


@pytest.mark.asyncio
async def test_real_graph_lineage_is_exposed_without_republishing_or_dropping_edges(
    client: Elasticsearch,
    publications: TopicPublicationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = GraphStore(
        client, GraphStoreConfig(index=f"availability_graph_{uuid4().hex}")
    )
    client.indices.create(
        index=store.index,
        **load_definitions()["analysis_graph"],
    )
    try:
        publish(publications, "v1")
        pointer = GraphVersionPointer(
            signal=Signal.TOPIC,
            graph_version="graph",
            source_model_version="v1",
            congresses=[119],
        )
        edge = MemberEdge(
            graph_version="graph",
            signal=Signal.TOPIC,
            member="A",
            neighbor="B",
            score=0.8,
        )
        client.index(
            index=store.index,
            id=edge.id,
            document=edge.model_dump(mode="json"),
            refresh=True,
        )
        store.publish(pointer)
        members = Mock(spec=MemberService)
        members.get_summaries.return_value = {
            "B": MemberSummary(
                bioguide_id="B", display_name="Member B", party="Democratic", state="CA"
            )
        }
        graph = GraphService(store, members, publications)
        monkeypatch.setitem(app.dependency_overrides, get_graph_service, lambda: graph)
        path = "/api/v1/members/A/similar?signal=topic"
        assert (await get(path)).json()["analysis"]["state"] == "available"
        publish(publications, "v2")
        stale = await get(path)
        assert stale.status_code == 200
        assert stale.json()["analysis"]["state"] == "stale"
        assert stale.json()["similar"][0]["member"]["bioguide_id"] == "B"
        assert store.active_pointer(Signal.TOPIC) == pointer
        assert client.get(index=store.index, id=edge.id)["_source"] == edge.model_dump(
            mode="json"
        )
    finally:
        client.indices.delete(index=store.index, ignore_unavailable=True)

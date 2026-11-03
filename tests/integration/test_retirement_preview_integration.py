import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from cdm.config import AppConfig, ElasticConfig
from cdm.config.topic_analysis import (
    EmbeddingCache,
    GraphStoreConfig,
    PerspectiveKind,
    PerspectiveSchema,
)
from cdm.graph.models import GraphVersionPointer, Signal
from cdm.graph.store import GraphStore
from cdm.store.perspective_repository import (
    PerspectivePublication,
    PerspectiveRepository,
)
from cdm.store.topic_publication import (
    TopicPublicationStore,
    TopicRunCounts,
    TopicRunSpecification,
)
from cdm.topics.retirement import (
    ReferenceKind,
    ReferenceState,
    RetirementReport,
    RetirementReporter,
)
from scripts import preview_analytics_retirement


@pytest.fixture
def stores() -> Iterator[tuple[TopicPublicationStore, GraphStore, str, str]]:
    url = os.environ.get("RETIREMENT_PREVIEW_TEST_URL")
    if not url:
        pytest.skip(
            "Set RETIREMENT_PREVIEW_TEST_URL to an isolated Elasticsearch server"
        )
    client = Elasticsearch(url, request_timeout=30)
    prefix = f"retirement-preview-test-{uuid4().hex}"
    publications = TopicPublicationStore(client, f"{prefix}-analysis")
    graphs = GraphStore(client, GraphStoreConfig(index=f"{prefix}-graph"))
    cache = f"{prefix}-cache"
    source = f"{prefix}-source"
    try:
        publications.ensure_index()
        client.indices.put_mapping(
            index=publications.index, properties=PerspectiveSchema.properties()
        )
        client.indices.create(index=graphs.index)
        client.indices.create(
            index=cache,
            mappings=EmbeddingCache(
                index=cache, model="model", dimensions=2
            ).mappings(),
        )
        client.index(
            index=cache,
            id="bill",
            document={"model": "model", "embedding": [1.0, 0.0]},
            refresh="wait_for",
        )
        client.index(
            index=source,
            id="bill",
            document={"title": "Congressional source record", "congress": 119},
            refresh="wait_for",
        )
        yield publications, graphs, cache, source
    finally:
        for index in (publications.index, graphs.index, cache, source):
            client.indices.delete(index=index, ignore_unavailable=True)
        client.close()


def write_run(
    publications: TopicPublicationStore, version: str, cache: str, path: Path
) -> None:
    run = TopicRunSpecification(
        model_version=version,
        trained_at=datetime.now(UTC),
        embedding_model="model",
        embedding_cache=EmbeddingCache(index=cache, model="model", dimensions=2),
        min_congress=113,
        corpus_size=1,
        dated_documents=0,
        model_path=str(path),
        counts=TopicRunCounts(
            topics=1,
            assignments=1,
            over_time=0,
            metasubjects=1,
            metasubject_over_time=0,
        ),
    )
    publications.write(
        run,
        (
            {
                "_index": publications.index,
                "_id": f"{kind}:{version}",
                "kind": kind,
                "model_version": version,
            }
            for kind, count in run.counts.by_kind().items()
            if count
        ),
    )


def test_real_inventory_is_read_only_paginated_and_follows_live_replacements(
    stores: tuple[TopicPublicationStore, GraphStore, str, str], tmp_path: Path
) -> None:
    publications, graphs, cache, source = stores
    client = publications.client
    artifact = tmp_path / "old-model"
    artifact.write_bytes(b"untouched model artifact")
    write_run(publications, "old", cache, artifact)
    write_run(publications, "current", cache, tmp_path / "current")
    publications.publish("current", None)
    graphs.publish(
        GraphVersionPointer(
            signal=Signal.TOPIC, graph_version="g", source_model_version="old"
        )
    )
    written, errors = bulk(
        client,
        (
            {
                "_index": publications.index,
                "_id": f"legacy:{number}",
                "kind": PerspectiveKind.PARTY_TOPIC,
                "congress": 118,
                "model_version": "old" if number == 10004 else "current",
            }
            for number in range(10005)
        ),
        refresh="wait_for",
    )
    assert written == 10005 and not errors
    perspectives = PerspectiveRepository(client, publications.index)
    perspectives.replace(119, "current", datetime.now(UTC), [])
    reporter = RetirementReporter(publications, graphs, "untouched-legacy-cache")
    before = {
        index: client.count(index=index)["count"]
        for index in (publications.index, graphs.index, cache, source)
    }
    source_before = client.get(index=source, id="bill").body
    cache_before = client.get(index=cache, id="bill").body

    with patch.object(
        client.transport, "perform_request", wraps=client.transport.perform_request
    ) as requests:
        report = reporter.report()

    assert not report.deletion_authorized
    assert all(review.state == ReferenceState.REFERENCED for review in report.runs)
    assert {
        ref.model_version
        for ref in report.references
        if ref.kind == ReferenceKind.LEGACY_PERSPECTIVES
    } == {"current", "old"}
    assert all(len(review.cache_shared_with) == 1 for review in report.runs)
    for request in requests.call_args_list:
        method, target = request.args[:2]
        path = target.split("?")[0]
        assert (
            method in {"GET", "HEAD"}
            or method == "POST"
            and path in {f"/{publications.index}/_search", "/_search/scroll"}
            or method == "DELETE"
            and path == "/_search/scroll"
        ), (method, path)
    assert {index: client.count(index=index)["count"] for index in before} == before
    assert client.get(index=source, id="bill").body == source_before
    assert client.get(index=cache, id="bill").body == cache_before
    assert artifact.read_bytes() == b"untouched model artifact"

    graphs.publish(
        GraphVersionPointer(
            signal=Signal.TOPIC,
            graph_version="replacement",
            source_model_version="current",
        )
    )
    assert reporter.report().runs[1].state == ReferenceState.REFERENCED
    # An empty same-Congress snapshot still supersedes all of its legacy rows.
    perspectives.replace(118, "current", datetime.now(UTC), [])
    refreshed = reporter.report()
    assert refreshed.runs[1].run.model_version == "old"
    assert refreshed.runs[1].state == ReferenceState.UNREFERENCED
    assert not refreshed.deletion_authorized
    assert not any(
        ref.kind == ReferenceKind.LEGACY_PERSPECTIVES for ref in refreshed.references
    )
    assert (
        client.count(
            index=publications.index,
            query={"term": {"kind": PerspectiveKind.PARTY_TOPIC}},
        )["count"]
        == 10005
    )
    assert client.exists(
        index=publications.index, id=PerspectivePublication.document_id(118)
    )

    graphs.publish(GraphVersionPointer(signal=Signal.TOPIC, graph_version="legacy"))
    assert reporter.report().runs[1].state == ReferenceState.UNKNOWN
    assert artifact.read_bytes() == b"untouched model artifact"


def test_actual_cli_and_container_emit_valid_json_without_a_job_or_model_build(
    stores: tuple[TopicPublicationStore, GraphStore, str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    publications, _, cache, _ = stores
    write_run(publications, "current", cache, tmp_path / "model-not-loaded")
    publications.publish("current", None)
    config = AppConfig(
        elastic=ElasticConfig(
            es_local_url=os.environ["RETIREMENT_PREVIEW_TEST_URL"],
            es_local_api_key="isolated-test-key",
            analysis_index=publications.index,
        )
    )
    monkeypatch.setattr(preview_analytics_retirement, "get_config", lambda: config)
    monkeypatch.setattr("sys.argv", ["preview_analytics_retirement"])

    preview_analytics_retirement.main()

    report = RetirementReport.model_validate_json(capsys.readouterr().out)
    assert not report.deletion_authorized
    assert len(report.runs) == 1
    assert report.runs[0].state == ReferenceState.REFERENCED
    assert report.runs[0].cache_state == ReferenceState.REFERENCED
    assert report.warnings == []

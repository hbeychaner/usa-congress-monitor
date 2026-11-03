import json
from datetime import UTC, datetime
from unittest.mock import Mock, call, patch

import pytest
from elasticsearch import Elasticsearch
from pydantic import ValidationError

from cdm.config.topic_analysis import EmbeddingCache, PerspectiveKind, TopicKind
from cdm.graph.models import GraphVersionPointer, Signal
from cdm.graph.store import GraphStore
from cdm.store.perspective_repository import PerspectivePublication
from cdm.store.topic_publication import (
    CompletedTopicRun,
    TopicPublicationStore,
    TopicRunCounts,
)
from cdm.topics.retirement import (
    ReferenceKind,
    ReferenceState,
    RetirementReporter,
)
from cdm.utils.json_types import JsonObject
from scripts import preview_analytics_retirement


def completed(version: str, cache: str | None = "shared-cache") -> CompletedTopicRun:
    return CompletedTopicRun(
        model_version=version,
        trained_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        embedding_model="model",
        embedding_cache=EmbeddingCache(index=cache, model="model", dimensions=2)
        if cache
        else None,
        min_congress=113,
        corpus_size=1,
        dated_documents=0,
        model_path=f"custom-model-root/{version}",
        counts=TopicRunCounts(
            topics=1,
            assignments=1,
            over_time=0,
            metasubjects=1,
            metasubject_over_time=0,
        ),
    )


def manifest(run: CompletedTopicRun) -> JsonObject:
    return {"_id": run.id, "_source": run.model_dump(mode="json")}


def perspective(
    version: str | None,
    congress: int,
    kind: PerspectiveKind = PerspectiveKind.PUBLICATION,
) -> JsonObject:
    return {
        "_id": PerspectivePublication.document_id(congress)
        if kind == PerspectiveKind.PUBLICATION
        else f"legacy:{congress}:{version}",
        "_source": {
            "kind": kind,
            "congress": congress,
            "model_version": version,
        },
    }


@pytest.fixture
def publications() -> Mock:
    client = Mock(spec=Elasticsearch, indices=Mock())
    client.indices.exists.return_value = True
    publications = Mock(
        spec=TopicPublicationStore, client=client, index="analysis-test"
    )
    publications.current.return_value = completed("current")
    return publications


@pytest.fixture
def graphs() -> Mock:
    graphs = Mock(spec=GraphStore)
    graphs.active_pointer.return_value = None
    return graphs


def test_report_preserves_all_live_references_and_shows_shared_caches(
    publications: Mock, graphs: Mock
) -> None:
    runs = [completed(version) for version in ("current", "graph", "party", "unused")]
    graphs.active_pointer.return_value = GraphVersionPointer(
        signal=Signal.TOPIC, graph_version="g", source_model_version="graph"
    )
    with patch(
        "cdm.topics.retirement.scan",
        return_value=[*(manifest(run) for run in runs), perspective("party", 119)],
    ) as scanner:
        report = RetirementReporter(publications, graphs, "legacy-cache").report()

    assert {review.run.model_version: review.state for review in report.runs} == {
        "current": ReferenceState.REFERENCED,
        "graph": ReferenceState.REFERENCED,
        "party": ReferenceState.REFERENCED,
        "unused": ReferenceState.UNREFERENCED,
    }
    unused = next(
        review for review in report.runs if review.run.model_version == "unused"
    )
    assert unused.cache_shared_with == ["current", "graph", "party"]
    assert unused.cache_state == ReferenceState.REFERENCED
    assert report.current_run == publications.current.return_value
    assert unused.run.model_path == "custom-model-root/unused"
    assert report.legacy_embedding_index == "legacy-cache"
    assert not report.deletion_authorized and report.limitations
    assert report.warnings == []
    assert scanner.call_args.kwargs["allow_partial_search_results"] is False
    query = scanner.call_args.kwargs["query"]
    assert query["query"] == {"terms": {"kind": [TopicKind.RUN, *PerspectiveKind]}}
    assert "results" not in query["_source"]
    graphs.active_pointer.assert_called_once_with(Signal.TOPIC)
    client = publications.client
    for operation in ("index", "delete", "delete_by_query", "bulk", "update"):
        getattr(client, operation).assert_not_called()
    assert client.indices.mock_calls == [call.exists(index="analysis-test")]
    publications.ensure_index.assert_not_called()
    publications.write.assert_not_called()
    publications.publish.assert_not_called()
    graphs.publish.assert_not_called()


@pytest.mark.parametrize("unknown", ["graph", "legacy", "snapshot"])
def test_unknown_consumer_lineage_never_means_unreferenced(
    publications: Mock, graphs: Mock, unknown: str
) -> None:
    hits = [manifest(completed("current")), manifest(completed("older"))]
    if unknown == "graph":
        graphs.active_pointer.return_value = GraphVersionPointer(
            signal=Signal.TOPIC, graph_version="legacy"
        )
    else:
        hits.append(
            perspective(
                None,
                118,
                PerspectiveKind.PARTY_TOPIC
                if unknown == "legacy"
                else PerspectiveKind.PUBLICATION,
            )
        )
    with patch("cdm.topics.retirement.scan", return_value=hits):
        report = RetirementReporter(publications, graphs, "legacy").report()
    assert report.runs[0].state == ReferenceState.REFERENCED
    assert report.runs[1].state == ReferenceState.UNKNOWN
    assert any("unknown topic lineage" in warning for warning in report.warnings)


def test_only_same_congress_snapshots_supersede_legacy_rows(
    publications: Mock, graphs: Mock
) -> None:
    with patch(
        "cdm.topics.retirement.scan",
        return_value=[
            manifest(completed("current")),
            manifest(completed("old")),
            perspective(None, 118, PerspectiveKind.PARTY_TOPIC),
            perspective("current", 118),
            perspective("old", 117, PerspectiveKind.PARTY_TOPIC),
            perspective("other-old", 117, PerspectiveKind.PARTY_TOPIC),
            perspective("old", 117, PerspectiveKind.PARTY_TOPIC),
        ],
    ):
        report = RetirementReporter(publications, graphs, "legacy").report()
    legacy = [
        ref
        for ref in report.references
        if ref.kind == ReferenceKind.LEGACY_PERSPECTIVES
    ]
    assert {(ref.congress, ref.model_version) for ref in legacy} == {
        (117, "old"),
        (117, "other-old"),
    }
    assert report.runs[1].state == ReferenceState.REFERENCED
    assert any("other-old" in warning for warning in report.warnings)
    assert not any("unknown topic lineage" in warning for warning in report.warnings)


def test_missing_publication_and_cache_metadata_are_explicit(
    publications: Mock, graphs: Mock
) -> None:
    publications.current.return_value = None
    with patch(
        "cdm.topics.retirement.scan", return_value=[manifest(completed("old", None))]
    ):
        report = RetirementReporter(publications, graphs, "legacy").report()
    assert report.runs[0].state == ReferenceState.UNKNOWN
    assert report.unknown_cache_versions == ["old"]
    assert any("No published topic run" in warning for warning in report.warnings)
    assert any("cache ownership is unknown" in warning for warning in report.warnings)


def test_missing_index_is_an_empty_inventory_without_creating_it(
    publications: Mock, graphs: Mock
) -> None:
    publications.current.return_value = None
    publications.client.indices.exists.return_value = False
    with patch("cdm.topics.retirement.scan") as scanner:
        report = RetirementReporter(publications, graphs, "legacy").report()
    assert report.runs == []
    assert report.warnings
    scanner.assert_not_called()
    publications.client.indices.create.assert_not_called()


def test_missing_manifest_still_protects_the_current_pointers_known_cache(
    publications: Mock, graphs: Mock
) -> None:
    with patch("cdm.topics.retirement.scan", return_value=[manifest(completed("old"))]):
        report = RetirementReporter(publications, graphs, "legacy").report()
    assert report.runs[0].state == ReferenceState.UNREFERENCED
    assert report.runs[0].cache_state == ReferenceState.REFERENCED
    assert report.runs[0].cache_shared_with == ["current"]
    assert report.unknown_cache_versions == []
    assert any("without validated manifests" in warning for warning in report.warnings)


@pytest.mark.parametrize("unknown_manifest", [False, True])
def test_unknown_cache_ownership_cannot_mark_a_cache_unreferenced(
    publications: Mock, graphs: Mock, unknown_manifest: bool
) -> None:
    hits = [
        manifest(completed("current")),
        manifest(completed("unused", "other-cache")),
    ]
    if unknown_manifest:
        hits.append(manifest(completed("legacy", None)))
    else:
        hits.append(perspective("legacy", 118))
    with patch("cdm.topics.retirement.scan", return_value=hits):
        report = RetirementReporter(publications, graphs, "legacy-cache").report()
    unused = next(
        review for review in report.runs if review.run.model_version == "unused"
    )
    assert unused.state == ReferenceState.UNREFERENCED
    assert unused.cache_state == ReferenceState.UNKNOWN
    assert report.unknown_cache_versions == ["legacy"]


def test_unreferenced_cache_is_distinct_from_a_shared_referenced_cache(
    publications: Mock, graphs: Mock
) -> None:
    with patch(
        "cdm.topics.retirement.scan",
        return_value=[
            manifest(completed("current")),
            manifest(completed("old", "different-cache")),
        ],
    ):
        report = RetirementReporter(publications, graphs, "legacy").report()
    assert report.runs[1].state == ReferenceState.UNREFERENCED
    assert report.runs[1].cache_state == ReferenceState.UNREFERENCED
    assert report.runs[1].cache_shared_with == []


@pytest.mark.parametrize("failure", ["scan", "publication", "graph"])
def test_dependency_failures_are_not_success_shaped_empty_reports(
    publications: Mock, graphs: Mock, failure: str
) -> None:
    if failure == "publication":
        publications.current.side_effect = RuntimeError("unavailable")
    if failure == "graph":
        graphs.active_pointer.side_effect = RuntimeError("unavailable")
    with (
        patch(
            "cdm.topics.retirement.scan",
            side_effect=RuntimeError("unavailable") if failure == "scan" else None,
            return_value=[],
        ),
        pytest.raises(RuntimeError, match="unavailable"),
    ):
        RetirementReporter(publications, graphs, "legacy").report()


@pytest.mark.parametrize("kind", ["manifest", "perspective", "graph", "malformed"])
def test_corrupt_documents_do_not_produce_retirement_advice(
    publications: Mock, graphs: Mock, kind: str
) -> None:
    hit = manifest(completed("current"))
    if kind == "manifest":
        hit["_id"] = "wrong"
    elif kind == "perspective":
        hit = perspective("current", 118)
        hit["_id"] = "wrong"
    elif kind == "graph":
        graphs.active_pointer.return_value = GraphVersionPointer(
            signal=Signal.VOTING, graph_version="wrong"
        )
    else:
        hit = {"_id": "bad", "_source": {"kind": TopicKind.RUN}}
    with (
        patch("cdm.topics.retirement.scan", return_value=[hit]),
        pytest.raises((ValueError, ValidationError)),
    ):
        RetirementReporter(publications, graphs, "legacy").report()


def test_cli_help_never_initializes_configuration_or_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", ["preview_analytics_retirement", "--help"])
    with (
        patch.object(preview_analytics_retirement, "get_config") as config,
        patch.object(preview_analytics_retirement, "Container") as container,
        pytest.raises(SystemExit) as exit_info,
    ):
        preview_analytics_retirement.main()
    assert exit_info.value.code == 0
    config.assert_not_called()
    container.assert_not_called()


@pytest.mark.parametrize("failed", [False, True])
def test_cli_prints_report_and_closes_client_even_on_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failed: bool,
) -> None:
    monkeypatch.setattr("sys.argv", ["preview_analytics_retirement"])
    container = Mock()
    container.retirement_reporter.report.return_value.model_dump_json.return_value = (
        '{"deletion_authorized": false}'
    )
    if failed:
        container.retirement_reporter.report.side_effect = RuntimeError("unavailable")
    with (
        patch.object(preview_analytics_retirement, "get_config"),
        patch.object(preview_analytics_retirement, "Container", return_value=container),
    ):
        if failed:
            with pytest.raises(RuntimeError, match="unavailable"):
                preview_analytics_retirement.main()
            assert capsys.readouterr().out == ""
        else:
            preview_analytics_retirement.main()
            assert json.loads(capsys.readouterr().out) == {"deletion_authorized": False}
    container.elastic_client.close.assert_called_once_with()
    container.analytics_jobs.submit.assert_not_called()

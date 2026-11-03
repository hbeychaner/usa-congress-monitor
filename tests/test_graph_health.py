from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest

from cdm.graph.health import GraphHealthChecker, HealthState
from cdm.graph.models import GraphBuildStatus, GraphVersionPointer, Signal
from cdm.graph.store import GraphStore
from cdm.store.topic_publication import TopicPublicationStore

NOW = datetime(2026, 10, 9, tzinfo=UTC)


class FakeStore(GraphStore):
    def __init__(
        self, pointers: dict[Signal, GraphVersionPointer], edges: int = 5
    ) -> None:
        self.pointers, self.edges = pointers, edges

    def active_pointer(self, signal: Signal) -> GraphVersionPointer | None:
        return self.pointers.get(signal)

    def edge_count(self, signal: Signal, graph_version: str) -> int:
        return self.edges

    def schema_errors(self) -> list[str]:
        return []


def _checker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    pointers,
    edges: int = 5,
    topic_model: str | None = "published-model",
) -> GraphHealthChecker:
    checker = GraphHealthChecker(
        FakeStore(pointers, edges),
        Mock(spec=TopicPublicationStore),
        GraphBuildStatus,
        now=NOW,
    )
    monkeypatch.setattr(checker, "_topic_model_version", lambda: topic_model)
    return checker


def _pointers(
    version: str = "20261008T000000Z", age_days: int = 1
) -> dict[Signal, GraphVersionPointer]:
    return {
        signal: GraphVersionPointer(
            signal=signal,
            graph_version=version,
            built_at=NOW - timedelta(days=age_days),
            source_model_version="published-model" if signal is Signal.TOPIC else None,
            congresses=[118],
        )
        for signal in Signal
    }


def test_fresh_graph_is_ok(monkeypatch, tmp_path):
    assert _checker(monkeypatch, tmp_path, _pointers()).check().state is HealthState.OK


def test_missing_signal_fails(monkeypatch, tmp_path):
    pointers = _pointers()
    del pointers[Signal.VOTING]
    report = _checker(monkeypatch, tmp_path, pointers).check()
    assert report.state is HealthState.FAILED
    assert "member graph voting: no published graph version" in report.warnings


def test_empty_version_fails(monkeypatch, tmp_path):
    assert (
        _checker(monkeypatch, tmp_path, _pointers(), edges=0).check().state
        is HealthState.FAILED
    )


def test_old_graph_warns(monkeypatch, tmp_path):
    report = _checker(monkeypatch, tmp_path, _pointers(age_days=12)).check()
    assert report.state is HealthState.WARNING


def test_topic_graph_with_different_source_model_warns(monkeypatch, tmp_path):
    report = _checker(
        monkeypatch, tmp_path, _pointers(), topic_model="20261009T000000Z"
    ).check()
    assert report.state is HealthState.WARNING
    assert [w for w in report.warnings if "different topic model" in w]


def test_newer_graph_timestamp_does_not_hide_source_drift(monkeypatch, tmp_path):
    report = _checker(
        monkeypatch, tmp_path, _pointers(), topic_model="000-new-published-model"
    ).check()
    assert report.state is HealthState.WARNING
    assert [w for w in report.warnings if "different topic model" in w]


def test_matching_source_is_fresh_regardless_of_version_order(monkeypatch, tmp_path):
    report = _checker(
        monkeypatch, tmp_path, _pointers(), topic_model="published-model"
    ).check()
    assert report.state is HealthState.OK
    topic = next(item for item in report.signals if item.signal is Signal.TOPIC)
    assert topic.source_model_version == "published-model"
    assert topic.congresses == [118]


def test_legacy_topic_graph_has_unknown_lineage(monkeypatch, tmp_path):
    pointers = _pointers()
    pointers[Signal.TOPIC] = GraphVersionPointer(
        signal=Signal.TOPIC, graph_version="20990101T000000Z", built_at=NOW
    )
    report = _checker(monkeypatch, tmp_path, pointers).check()
    assert report.state is HealthState.WARNING
    assert [w for w in report.warnings if "source topic model is unknown" in w]


def test_topic_graph_without_published_model_warns(monkeypatch, tmp_path):
    report = _checker(monkeypatch, tmp_path, _pointers(), topic_model=None).check()
    assert report.state is HealthState.WARNING
    assert [w for w in report.warnings if "no published topic model" in w]


def test_freshness_reads_exact_published_identity() -> None:
    publications = Mock(spec=TopicPublicationStore)
    publications.current.return_value = Mock(
        model_version="published-uuid", trained_at=NOW
    )
    checker = GraphHealthChecker(FakeStore({}), publications, GraphBuildStatus, now=NOW)
    assert checker._topic_model_version() == "published-uuid"


def test_legacy_congress_coverage_is_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pointers = _pointers()
    pointers[Signal.VOTING].congresses = None
    report = _checker(monkeypatch, tmp_path, pointers).check()
    assert report.state is HealthState.WARNING
    assert any(
        "source Congress coverage is unknown" in item for item in report.warnings
    )


def test_schema_drift_fails_health(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    checker = _checker(monkeypatch, tmp_path, _pointers())
    monkeypatch.setattr(
        checker.store, "schema_errors", lambda: ["shared_topics: missing mapping"]
    )
    report = checker.check()
    assert report.state is HealthState.FAILED
    assert "shared_topics: missing mapping" in report.warnings

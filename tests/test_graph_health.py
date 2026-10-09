from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from cdm.graph import health as health_module
from cdm.graph.health import GraphHealthChecker, HealthState
from cdm.graph.models import GraphVersionPointer, Signal
from cdm.graph.runner import GraphBuildRunner

NOW = datetime(2026, 10, 9, tzinfo=UTC)


class FakeStore:
    def __init__(self, pointers: dict[Signal, GraphVersionPointer], edges: int = 5) -> None:
        self.pointers, self.edges = pointers, edges

    def active_pointer(self, signal: Signal) -> GraphVersionPointer | None:
        return self.pointers.get(signal)

    def edge_count(self, signal: Signal, graph_version: str) -> int:
        return self.edges


def _checker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, pointers, edges: int = 5, topic_model: str | None = None
) -> GraphHealthChecker:
    monkeypatch.setattr(health_module, "GraphStore", lambda client: FakeStore(pointers, edges))
    checker = GraphHealthChecker(None, GraphBuildRunner(tmp_path / "s.json"), now=NOW)
    monkeypatch.setattr(checker, "_topic_model_version", lambda: topic_model)
    return checker


def _pointers(version: str = "20261008T000000Z", age_days: int = 1) -> dict[Signal, GraphVersionPointer]:
    return {
        signal: GraphVersionPointer(
            signal=signal, graph_version=version, built_at=NOW - timedelta(days=age_days)
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
    assert _checker(monkeypatch, tmp_path, _pointers(), edges=0).check().state is HealthState.FAILED


def test_old_graph_warns(monkeypatch, tmp_path):
    report = _checker(monkeypatch, tmp_path, _pointers(age_days=12)).check()
    assert report.state is HealthState.WARNING


def test_topic_graph_older_than_model_warns(monkeypatch, tmp_path):
    report = _checker(monkeypatch, tmp_path, _pointers(), topic_model="20261009T000000Z").check()
    assert report.state is HealthState.WARNING
    assert [w for w in report.warnings if "retrained" in w]

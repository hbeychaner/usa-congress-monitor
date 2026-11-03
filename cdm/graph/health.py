"""Health of the published member graph: presence, size, freshness, source drift."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from cdm.config.topic_analysis import GraphHealthConfig
from cdm.graph.models import BuildState, GraphBuildStatus, Signal
from cdm.graph.store import GraphStore
from cdm.store.topic_publication import TopicPublicationStore


class HealthState(StrEnum):
    OK = "ok"
    WARNING = "warning"
    FAILED = "failed"


class SignalHealth(BaseModel):
    signal: Signal
    state: HealthState = HealthState.OK
    graph_version: str | None = None
    source_model_version: str | None = None
    congresses: list[int] | None = None
    built_at: datetime | None = None
    edge_count: int = 0
    problems: list[str] = Field(default_factory=list)


class GraphHealth(BaseModel):
    state: HealthState = HealthState.OK
    signals: list[SignalHealth] = Field(default_factory=list)
    last_build_state: BuildState = BuildState.IDLE
    warnings: list[str] = Field(default_factory=list)


class GraphHealthChecker:
    """Inspects the live graph versions without changing anything."""

    def __init__(
        self,
        store: GraphStore,
        publications: TopicPublicationStore,
        status: Callable[[], GraphBuildStatus],
        now: datetime | None = None,
        settings: GraphHealthConfig | None = None,
    ) -> None:
        self.store = store
        self._publications = publications
        self._settings = settings or GraphHealthConfig()
        self._status = status
        self.now = now or datetime.now(UTC)

    def _topic_model_version(self) -> str | None:
        run = self._publications.current()
        return run.model_version if run else None

    def _check_signal(self, signal: Signal, topic_model: str | None) -> SignalHealth:
        health = SignalHealth(signal=signal)
        pointer = self.store.active_pointer(signal)
        if pointer is None:
            health.state = HealthState.FAILED
            health.problems.append("no published graph version")
            return health
        health.graph_version = pointer.graph_version
        health.source_model_version = pointer.source_model_version
        health.congresses = pointer.congresses
        health.built_at = pointer.built_at
        if pointer.congresses is None:
            health.problems.append("source Congress coverage is unknown; rebuild graph")
        health.edge_count = self.store.edge_count(signal, pointer.graph_version)
        if health.edge_count == 0:
            health.state = HealthState.FAILED
            health.problems.append("published version has no edges")
        if self.now - pointer.built_at > self._settings.max_age:
            health.problems.append(
                f"built more than {self._settings.max_age.days} days ago"
            )
        if signal is Signal.TOPIC:
            if pointer.source_model_version is None:
                health.problems.append("source topic model is unknown; rebuild graph")
            elif topic_model is None:
                health.problems.append("no published topic model")
            elif pointer.source_model_version != topic_model:
                health.problems.append("graph uses a different topic model")
        if health.problems and health.state is HealthState.OK:
            health.state = HealthState.WARNING
        return health

    def check(self) -> GraphHealth:
        topic_model = self._topic_model_version()
        signals = [self._check_signal(signal, topic_model) for signal in Signal]
        report = GraphHealth(signals=signals, last_build_state=self._status().state)
        schema_errors = self.store.schema_errors()
        if schema_errors:
            report.warnings.extend(schema_errors)
        for health in signals:
            report.warnings.extend(
                f"member graph {health.signal}: {problem}"
                for problem in health.problems
            )
        if report.last_build_state is BuildState.FAILED:
            report.warnings.append("member graph: last build failed")
        states = {health.state for health in signals}
        if HealthState.FAILED in states or schema_errors:
            report.state = HealthState.FAILED
        elif HealthState.WARNING in states or report.warnings:
            report.state = HealthState.WARNING
        return report

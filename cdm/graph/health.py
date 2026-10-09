"""Health of the published member graph: presence, size, freshness, source drift."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum

from elasticsearch import Elasticsearch, NotFoundError
from pydantic import BaseModel, Field

from cdm.graph.models import Signal
from cdm.graph.runner import BuildState, GraphBuildRunner
from cdm.graph.store import GraphStore
from cdm.graph.topics import TopicModelReader

MAX_AGE = timedelta(days=9)
VERSION_FORMAT = "%Y%m%dT%H%M%SZ"


class HealthState(StrEnum):
    OK = "ok"
    WARNING = "warning"
    FAILED = "failed"


class SignalHealth(BaseModel):
    signal: Signal
    state: HealthState = HealthState.OK
    graph_version: str | None = None
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
        client: Elasticsearch,
        runner: GraphBuildRunner | None = None,
        now: datetime | None = None,
    ) -> None:
        self.client = client
        self.store = GraphStore(client)
        self.runner = runner or GraphBuildRunner()
        self.now = now or datetime.now(UTC)

    def _topic_model_version(self) -> str | None:
        try:
            return TopicModelReader(self.client).latest_version()
        except NotFoundError:
            return None

    def _check_signal(self, signal: Signal, topic_model: str | None) -> SignalHealth:
        health = SignalHealth(signal=signal)
        pointer = self.store.active_pointer(signal)
        if pointer is None:
            health.state = HealthState.FAILED
            health.problems.append("no published graph version")
            return health
        health.graph_version = pointer.graph_version
        health.built_at = pointer.built_at
        health.edge_count = self.store.edge_count(signal, pointer.graph_version)
        if health.edge_count == 0:
            health.state = HealthState.FAILED
            health.problems.append("published version has no edges")
        if self.now - pointer.built_at > MAX_AGE:
            health.problems.append(f"built more than {MAX_AGE.days} days ago")
        if (
            signal is Signal.TOPIC
            and topic_model
            and pointer.graph_version < topic_model
        ):
            health.problems.append("topic model retrained since this graph was built")
        if health.problems and health.state is HealthState.OK:
            health.state = HealthState.WARNING
        return health

    def check(self) -> GraphHealth:
        topic_model = self._topic_model_version()
        signals = [self._check_signal(signal, topic_model) for signal in Signal]
        report = GraphHealth(
            signals=signals, last_build_state=self.runner.read().state
        )
        for health in signals:
            report.warnings.extend(
                f"member graph {health.signal}: {problem}" for problem in health.problems
            )
        if report.last_build_state is BuildState.FAILED:
            report.warnings.append("member graph: last build failed")
        states = {health.state for health in signals}
        if HealthState.FAILED in states:
            report.state = HealthState.FAILED
        elif HealthState.WARNING in states or report.warnings:
            report.state = HealthState.WARNING
        return report

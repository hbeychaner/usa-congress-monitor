"""Builds and publishes member graph signals, reporting progress to the runner."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, datetime
from uuid import uuid4

from cdm.graph.collaboration import CollaborationGraphBuilder
from cdm.graph.models import GraphVersionPointer, MemberEdge, Signal, StagedGraph
from cdm.graph.store import BillSignatureReader, GraphStore, RollCallReader
from cdm.graph.topics import TopicGraphBuilder, TopicModelReader
from cdm.graph.voting import VotingGraphBuilder
from cdm.jobs.analytics import AnalysisProgress


class GraphBuildJob:
    """Runs the requested signal builds and records stage, versions and outcome."""

    def __init__(
        self,
        store: GraphStore,
        bills: BillSignatureReader,
        rolls: RollCallReader,
        topics: TopicModelReader,
        report: Callable[[AnalysisProgress], None],
    ) -> None:
        self.store = store
        self._bills = bills
        self._rolls = rolls
        self._topics = topics
        self._report = report

    def _build(self, pointer: GraphVersionPointer) -> Iterator[MemberEdge]:
        version = pointer.graph_version
        if pointer.signal is Signal.VOTING:
            rolls = list(self._rolls.read())
            pointer.congresses = sorted({roll.congress for roll in rolls})
            return VotingGraphBuilder(rolls, version).build()
        bills = list(self._bills.read())
        pointer.congresses = sorted({bill.congress for bill in bills})
        if pointer.signal is Signal.COLLABORATION:
            return CollaborationGraphBuilder(bills, version).build()
        model = self._topics
        topic_version = model.latest_version()
        if topic_version is None:
            raise RuntimeError("no trained topic model; run topic training first")
        pointer.source_model_version = topic_version
        assignments = model.assignments(topic_version)
        return TopicGraphBuilder(
            bills, assignments, model.labels(topic_version), version
        ).build()

    def stage(self, signal: Signal) -> StagedGraph:
        """Write a candidate to the injected store without publishing its pointer."""
        pointer = GraphVersionPointer(
            signal=signal,
            graph_version=f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid4().hex}",
        )
        written = self.store.write_edges(self._build(pointer))
        pointer.built_at = datetime.now(UTC)
        return StagedGraph(pointer=pointer, written=written)

    def run(self, signals: Sequence[Signal] = ()) -> dict[Signal, str]:
        requested = list(signals) or list(Signal)
        versions: dict[Signal, str] = {}
        self.store.ensure_index()
        for signal in requested:
            self._report(AnalysisProgress(stage=signal.value, versions=versions))
            before = self.store.pointer_snapshot(signal)
            staged = self.stage(signal)
            pointer = staged.pointer
            self._report(AnalysisProgress(stage="publishing", versions=versions))
            self.store.publish(pointer, expected=before)
            versions[signal] = pointer.graph_version
            print(
                f"{signal}: wrote {staged.written:,} edges as {pointer.graph_version}"
            )
        self._report(AnalysisProgress(stage="done", progress=1.0, versions=versions))
        return versions

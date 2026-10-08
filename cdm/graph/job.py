"""Builds and publishes member graph signals, reporting progress to the runner."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, datetime

from elasticsearch import Elasticsearch

from cdm.graph.collaboration import CollaborationGraphBuilder
from cdm.graph.models import MemberEdge, Signal
from cdm.graph.runner import BuildState, GraphBuildRunner
from cdm.graph.store import BillSignatureReader, GraphStore, RollCallReader
from cdm.graph.voting import VotingGraphBuilder


class GraphBuildJob:
    """Runs the requested signal builds and records stage, versions and outcome."""

    def __init__(self, client: Elasticsearch, runner: GraphBuildRunner | None = None) -> None:
        self.client = client
        self.store = GraphStore(client)
        self.runner = runner

    def _builders(self) -> dict[Signal, Callable[[str], Iterator[MemberEdge]]]:
        return {
            Signal.COLLABORATION: self._collaboration_edges,
            Signal.VOTING: self._voting_edges,
        }

    def _collaboration_edges(self, version: str) -> Iterator[MemberEdge]:
        bills = list(BillSignatureReader(self.client).read())
        print(f"Read {len(bills):,} bills")
        return CollaborationGraphBuilder(bills, version).build()

    def _voting_edges(self, version: str) -> Iterator[MemberEdge]:
        rolls = list(RollCallReader(self.client).read())
        print(f"Read {len(rolls):,} roll calls")
        return VotingGraphBuilder(rolls, version).build()

    def _report(self, **fields: object) -> None:
        if self.runner is not None:
            self.runner.update(**fields)

    def run(self, signals: Sequence[Signal] = ()) -> dict[Signal, str]:
        builders = self._builders()
        requested = list(signals) or list(builders)
        versions: dict[Signal, str] = {}
        try:
            self.store.ensure_index()
            for signal in requested:
                self._report(stage=signal.value)
                version = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
                written = self.store.write_edges(builders[signal](version))
                self.store.publish(signal, version)
                stale = self.store.prune(signal)
                versions[signal] = version
                print(f"{signal}: wrote {written:,} edges as {version}; pruned: {stale or 'none'}")
        except Exception as error:
            self._report(
                state=BuildState.FAILED,
                message=str(error)[:500],
                finished_at=datetime.now(UTC),
            )
            raise
        self._report(
            state=BuildState.SUCCEEDED,
            stage="done",
            message=None,
            finished_at=datetime.now(UTC),
            versions=versions,
        )
        return versions

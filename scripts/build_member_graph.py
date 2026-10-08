"""Build member graph edges and publish the new version of each signal.

Usage:
    uv run python scripts/build_member_graph.py [collaboration] [voting]
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

from elasticsearch import Elasticsearch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdm.graph.collaboration import CollaborationGraphBuilder
from cdm.graph.models import Signal
from cdm.graph.store import BillSignatureReader, GraphStore, RollCallReader
from cdm.graph.voting import VotingGraphBuilder
from cdm.store.client import get_opensearch_client


def build_collaboration(client: Elasticsearch, store: GraphStore) -> None:
    version = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    bills = list(BillSignatureReader(client).read())
    print(f"Read {len(bills):,} bills")
    builder = CollaborationGraphBuilder(bills, version)
    publish(store, Signal.COLLABORATION, version, store.write_edges(builder.build()))


def build_voting(client: Elasticsearch, store: GraphStore) -> None:
    version = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    rolls = list(RollCallReader(client).read())
    print(f"Read {len(rolls):,} roll calls")
    builder = VotingGraphBuilder(rolls, version)
    publish(store, Signal.VOTING, version, store.write_edges(builder.build()))


def publish(store: GraphStore, signal: Signal, version: str, written: int) -> None:
    store.publish(signal, version)
    stale = store.prune(signal)
    print(f"{signal}: wrote {written:,} edges as {version}; pruned: {stale or 'none'}")


def main() -> None:
    client = get_opensearch_client()
    store = GraphStore(client)
    store.ensure_index()
    builders = {
        Signal.COLLABORATION: build_collaboration,
        Signal.VOTING: build_voting,
    }
    requested = [Signal(name) for name in sys.argv[1:]] or list(builders)
    for signal in requested:
        builders[signal](client, store)


if __name__ == "__main__":
    main()

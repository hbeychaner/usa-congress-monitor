"""Build the collaboration edges of the member graph and publish the new version.

Usage:
    uv run python scripts/build_member_graph.py
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdm.graph.collaboration import CollaborationGraphBuilder
from cdm.graph.models import Signal
from cdm.graph.store import BillSignatureReader, GraphStore
from cdm.store.client import get_opensearch_client


def main() -> None:
    client = get_opensearch_client()
    store = GraphStore(client)
    store.ensure_index()
    version = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    bills = list(BillSignatureReader(client).read())
    print(f"Read {len(bills):,} bills")
    builder = CollaborationGraphBuilder(bills, version)
    written = store.write_edges(builder.build())
    store.publish(Signal.COLLABORATION, version)
    stale = store.prune(Signal.COLLABORATION)
    print(f"Wrote {written:,} edges as {version}; pruned versions: {stale or 'none'}")


if __name__ == "__main__":
    main()

"""Ingest Voteview roll calls (both chambers) into the rollcall index.

Usage:
    uv run python scripts/ingest_votes.py                  # 113th through current
    uv run python scripts/ingest_votes.py --congress 119 --refresh
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdm.ingest.voteview import (
    FIRST_CONGRESS,
    VoteIngestor,
    VoteviewClient,
    current_congress,
)
from cdm.store.client import get_opensearch_client
from cdm.store.index_manager import IndexManager

CACHE_DIR = Path("data/voteview")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--congress", type=int, action="append")
    parser.add_argument("--refresh", action="store_true", help="Re-download the CSVs")
    args = parser.parse_args()

    client = get_opensearch_client()
    IndexManager(client).create("rollcall")
    ingestor = VoteIngestor(client, VoteviewClient(CACHE_DIR))
    current = current_congress(datetime.now(UTC).year)
    congresses = args.congress or range(FIRST_CONGRESS, current + 1)
    for congress, count in ingestor.ingest_range(
        congresses, refresh=args.refresh
    ).items():
        print(f"congress {congress}: {count} roll calls")


if __name__ == "__main__":
    main()

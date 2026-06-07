#!/usr/bin/env python3
"""Bulk download BILLSTATUS XML from GovInfo and save as items.json/items.jsonl.

This script is an alternative to the congress.gov API ingest path for bills.
It uses the GovInfo bulk data repository (no API key, no rate limits) and
produces output in the same format as the API ingest pipeline.

Usage examples:

    # Download all HR bills from the 118th Congress
    uv run python scripts/bulk_download_bills.py --congress 118 --types hr

    # Download all bill types for congress 118 + 119
    uv run python scripts/bulk_download_bills.py --congress 118 119 --outdir data/bulk

    # Quick smoke test: 10 bills from congress 118 hr
    uv run python scripts/bulk_download_bills.py --congress 118 --types hr --max-bills 10 --outdir /tmp/bulk_test

    # Resume an interrupted download
    uv run python scripts/bulk_download_bills.py --congress 118 --types hr --resume

    # Discover what congresses/types are available
    uv run python scripts/bulk_download_bills.py --list-congresses
    uv run python scripts/bulk_download_bills.py --list-types --congress 118
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Make sure the pycongress library (editable install or uv dep) is available.
# If running from within the Congress Tracker project, it should be on sys.path
# via pyproject.toml → [tool.uv.sources] or similar.
try:
    from congress_sdk.bulk import GovInfoBulkClient, BILL_TYPES
except ImportError as exc:
    sys.exit(
        f"ImportError: {exc}\n"
        "Make sure pycongress is installed (uv sync) or the PYTHONPATH is set."
    )


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    # Suppress noisy lower-level loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Download BILLSTATUS XML from GovInfo bulk data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Usage examples:")[1],
    )
    p.add_argument(
        "--congress",
        type=int,
        nargs="+",
        metavar="N",
        help="Congress number(s) to download (e.g. 118 119).",
    )
    p.add_argument(
        "--types",
        nargs="+",
        choices=BILL_TYPES,
        default=None,
        metavar="TYPE",
        help=f"Bill types to include. Defaults to all: {' '.join(BILL_TYPES)}",
    )
    p.add_argument(
        "--outdir",
        default="data/bills_bulk",
        help="Output directory. Each congress gets a subdirectory. (default: data/bills_bulk)",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=40,
        help="Concurrent download threads. (default: 40)",
    )
    p.add_argument(
        "--max-bills",
        type=int,
        default=None,
        metavar="N",
        help="Stop after N bills total (for testing).",
    )
    p.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip bills already saved in items.jsonl. (default: --resume)",
    )
    p.add_argument(
        "--list-congresses",
        action="store_true",
        help="Print available congress numbers and exit.",
    )
    p.add_argument(
        "--list-types",
        action="store_true",
        help="Print available bill types for --congress and exit.",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.verbose)
    log = logging.getLogger("bulk_download")

    client = GovInfoBulkClient()

    # ------------------------------------------------------------------
    # Discovery commands
    # ------------------------------------------------------------------
    if args.list_congresses:
        congresses = client.list_congresses()
        print("Available congresses:", " ".join(str(c) for c in congresses))
        return 0

    if args.list_types:
        if not args.congress:
            print("--list-types requires --congress", file=sys.stderr)
            return 1
        for c in args.congress:
            types = client.list_bill_types(c)
            print(f"Congress {c}: {' '.join(types)}")
        return 0

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    if not args.congress:
        print("--congress is required (e.g. --congress 118)", file=sys.stderr)
        return 1

    bill_types = args.types  # None means all

    # ------------------------------------------------------------------
    # Download loop
    # ------------------------------------------------------------------
    base_outdir = Path(args.outdir)
    total_saved = 0

    for congress in args.congress:
        outdir = base_outdir / str(congress)
        log.info(
            "=== Congress %d → %s (types=%s, workers=%d) ===",
            congress,
            outdir,
            bill_types or "all",
            args.workers,
        )

        records = client.download_congress(
            congress=congress,
            bill_types=bill_types,
            outdir=outdir,
            max_bills=args.max_bills,
            resume=args.resume,
        )

        total_saved += len(records)

        # Quick validation summary
        missing_id = sum(1 for r in records if not r.get("id"))
        missing_type = sum(1 for r in records if not r.get("type"))
        log.info(
            "Congress %d: %d bills, %d missing id, %d missing type",
            congress,
            len(records),
            missing_id,
            missing_type,
        )

        # Print a few sample records
        sample = records[:3]
        for r in sample:
            bill_id = r.get("id", "?")
            title = r.get("title", "")[:80]
            introduced = r.get("introducedDate", "?")
            n_actions = len(r.get("actions") or [])
            print(f"  {bill_id:30s}  {introduced}  {n_actions:3d} actions  {title}")

    log.info("Done. Total bills saved: %d", total_saved)
    return 0


if __name__ == "__main__":
    sys.exit(main())

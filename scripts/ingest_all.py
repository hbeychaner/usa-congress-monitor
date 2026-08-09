"""Bulk local ingest CLI — pull real API data for all (or selected) resources.

Examples
--------
# Ingest all date-windowed resources for January 2025:
python scripts/ingest_all.py --from-date 2025-01-01 --to-date 2025-01-31

# Ingest congress-scoped resources for the 119th Congress:
python scripts/ingest_all.py --congress 119 --scope congress_scoped

# Ingest static resources (congress list, house requirements, bound CR):
python scripts/ingest_all.py --scope static

# Ingest a specific subset with full item detail:
python scripts/ingest_all.py --from-date 2025-01-01 --to-date 2025-01-31 \\
    --resources amendment,nomination,crsreport --items

# Smoke-test: 1 page, no items, everything:
python scripts/ingest_all.py --from-date 2025-01-01 --to-date 2025-01-31 \\
    --max-pages 1 --outdir data/local_sample
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path when run directly
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdm.ingest.pipeline import Pipeline, PipelineConfig
from cdm.ingest.resource_config import RESOURCE_CONFIGS
from cdm.ingest.runner import Resource


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Bulk local ingest: pull Congress.gov data for all endpoints.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Date window
    p.add_argument(
        "--from-date",
        default=None,
        metavar="YYYY-MM-DD",
        help="Start of date window (ISO-8601). Applied to date-windowed resources.",
    )
    p.add_argument(
        "--to-date",
        default=None,
        metavar="YYYY-MM-DD",
        help="End of date window (ISO-8601). Applied to date-windowed resources.",
    )

    # Congress scope
    p.add_argument(
        "--congress",
        type=int,
        default=None,
        metavar="NUM",
        help="Congress number (e.g. 119). Required for congress-scoped resources.",
    )

    # Resource selection
    p.add_argument(
        "--scope",
        choices=["date_window", "congress_scoped", "static", "all"],
        default="all",
        help="Restrict to resources of this scope type (default: all).",
    )
    p.add_argument(
        "--resources",
        default=None,
        metavar="r1,r2,...",
        help="Comma-separated list of resource names to ingest (overrides --scope).",
    )

    # Output
    p.add_argument(
        "--outdir",
        default="data/local",
        help="Root directory for output files (default: data/local).",
    )

    # Item fetching
    p.add_argument(
        "--items",
        action="store_true",
        help="Fetch item-level detail for every list entry (slow; use with --max-items).",
    )
    p.add_argument(
        "--all-endpoints",
        action="store_true",
        help="With --items, attempt every registered item endpoint, including normally list-only resources.",
    )
    p.add_argument(
        "--max-items",
        type=int,
        default=None,
        metavar="N",
        help="Cap item fetches per resource.",
    )
    p.add_argument(
        "--max-pages",
        type=int,
        default=None,
        metavar="N",
        help="Cap list pages per resource (useful for smoke-tests).",
    )

    # Auth
    p.add_argument(
        "--api-key", default=None, help="Congress.gov API key (overrides env)."
    )

    # Error handling
    p.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first resource error (default: continue past errors).",
    )

    # Logging
    p.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO).",
    )

    return p.parse_args()


def _resolve_resources(args: argparse.Namespace) -> list[Resource]:
    """Return the list of Resource values to ingest, respecting --resources and --scope."""
    if args.resources:
        names = [n.strip() for n in args.resources.split(",") if n.strip()]
        resolved = []
        for name in names:
            try:
                resolved.append(Resource(name))
            except ValueError:
                valid = [r.value for r in Resource]
                print(
                    f"ERROR: unknown resource '{name}'. Valid values: {valid}",
                    file=sys.stderr,
                )
                sys.exit(1)
        return resolved

    from cdm.ingest.resource_config import (
        congress_scoped,
        date_windowed,
        static_resources,
    )

    if args.scope == "date_window":
        return [c.resource for c in date_windowed()]
    if args.scope == "congress_scoped":
        return [c.resource for c in congress_scoped()]
    if args.scope == "static":
        return [c.resource for c in static_resources()]
    # "all"
    return list(Resource)


def main() -> None:
    args = _parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("ingest_all")

    resources = _resolve_resources(args)

    # Warn if date-windowed resources selected but no date window given

    date_resources = [
        r for r in resources if RESOURCE_CONFIGS[r].scope == "date_window"
    ]
    if date_resources and not (args.from_date or args.to_date):
        logger.warning(
            "No --from-date / --to-date specified; date-windowed resources will "
            "return the API default (usually last 24 hours): %s",
            [r.value for r in date_resources],
        )

    congress_resources = [r for r in resources if RESOURCE_CONFIGS[r].requires_congress]
    if congress_resources and not args.congress:
        logger.error(
            "Resources %s require --congress but none was provided. "
            "They will be skipped.",
            [r.value for r in congress_resources],
        )

    def _normalize_date(d: str | None, end_of_day: bool = False) -> str | None:
        """Expand bare YYYY-MM-DD to full ISO-8601 required by the Congress.gov API."""
        if d is None:
            return None
        if "T" not in d:
            d = f"{d}T23:59:59Z" if end_of_day else f"{d}T00:00:00Z"
        return d

    cfg = PipelineConfig(
        outdir=Path(args.outdir),
        from_date=_normalize_date(args.from_date),
        to_date=_normalize_date(args.to_date, end_of_day=True),
        congress=args.congress,
        fetch_items=args.items,
        force_item_fetch=args.all_endpoints,
        max_pages=args.max_pages,
        max_items=args.max_items,
        api_key=args.api_key,
        skip_errors=not args.fail_fast,
    )

    logger.info(
        "Starting bulk ingest: %d resources → %s  (from=%s to=%s congress=%s)",
        len(resources),
        cfg.outdir,
        cfg.from_date or "—",
        cfg.to_date or "—",
        cfg.congress or "—",
    )

    pipeline = Pipeline(cfg)
    results = pipeline.run(resources)

    # Print summary table
    print("\n" + "=" * 60)
    print(f"{'Resource':<30} {'Status':<8} {'List':>6} {'Items':>6}")
    print("-" * 60)
    for r in results:
        status = "OK" if r.success else "FAIL"
        print(f"{r.resource.value:<30} {status:<8} {r.list_count:>6} {r.item_count:>6}")
        if r.error:
            print(f"  {'':30} ↳ {r.error}")
    print("=" * 60)
    failed = sum(1 for r in results if not r.success)
    print(f"Total: {len(results)} resources, {failed} failed")
    print(f"Output: {cfg.outdir.resolve()}")

    sys.exit(1 if failed and not cfg.skip_errors else 0)


if __name__ == "__main__":
    main()

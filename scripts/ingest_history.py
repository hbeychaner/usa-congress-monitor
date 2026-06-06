#!/usr/bin/env python3
"""Full-history ingest CLI — pull Congress.gov data for a multi-year / multi-congress span.

Strategy
────────
Resources have three scope types that each need a different iteration strategy:

  date_window    — Iterated year-by-year from --from-year to --to-year.
                   Each year is a separate pipeline run so progress is
                   incremental and easy to resume.

  congress_scoped— Run once per congress number in the congress range derived
                   from the year range (or overridden with --from-congress /
                   --to-congress).  house_vote and law are the main examples.

  static         — Run once (congress list, bound CR, house requirements).

Resume behaviour
────────────────
With --resume (default: on), a year/congress chunk is skipped when its output
directory already contains a non-empty list.json.  Re-run with --no-resume to
force a full re-fetch.

Examples
────────
    # Full 36-year ingest, list data only (safe default):
    python scripts/ingest_history.py

    # 1990–2010 only, no resume check:
    python scripts/ingest_history.py --from-year 1990 --to-year 2010 --no-resume

    # Bills + amendments only, with item-level detail:
    python scripts/ingest_history.py --resources bill,amendment --items

    # Smoke-test: 1 year, 1 page per resource:
    python scripts/ingest_history.py --from-year 2024 --to-year 2024 --max-pages 1
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdm.ingest.pipeline import Pipeline, PipelineConfig
from cdm.ingest.rate_limiter import TokenBucket
from cdm.ingest.resource_config import (
    RESOURCE_CONFIGS,
    date_windowed,
    congress_scoped,
    static_resources,
)
from cdm.ingest.runner import Resource

logger = logging.getLogger("ingest_history")

# ── Congress number ↔ year helpers ───────────────────────────────────────────

# Congress N convenes in odd year: start_year = 2*N + 1787
# e.g. 101 → 1989,  119 → 2025
_CONGRESS_START_YEAR = {n: 2 * n + 1787 for n in range(93, 125)}

# Reverse: first congress that starts in or before a given year
def _congress_for_year(year: int) -> int:
    return max(n for n, y in _CONGRESS_START_YEAR.items() if y <= year)


def _congresses_for_years(from_year: int, to_year: int) -> list[int]:
    """Return sorted list of congress numbers active during [from_year, to_year]."""
    result = []
    for n, start in _CONGRESS_START_YEAR.items():
        end = start + 1  # each congress spans 2 calendar years; +1 = start of next
        if start <= to_year and end >= from_year - 1:
            result.append(n)
    return sorted(result)


# ── Checkpoint helpers ────────────────────────────────────────────────────────

def _is_done(outdir: Path, resource: Resource, fetch_items: bool) -> bool:
    """Return True if this resource chunk is fully complete.

    - List is always required: list.json must exist and be non-empty.
    - Items: when fetch_items=True and the resource supports items,
      items.json must also exist and be non-empty.  We also accept
      items.jsonl (incremental file) as evidence of at-least-partial
      completion; the caller decides whether partial counts as done.
    """
    list_path = outdir / resource.value / "list.json"
    if not list_path.exists() or list_path.stat().st_size < 10:
        return False
    if not fetch_items:
        return True
    # Resources that are list-only (no item endpoint)
    from cdm.ingest.resource_config import RESOURCE_CONFIGS
    cfg = RESOURCE_CONFIGS.get(resource)
    if cfg and (cfg.list_only or not cfg.fetch_items_default):
        return True  # items not expected for this resource
    items_json = outdir / resource.value / "items.json"
    if items_json.exists() and items_json.stat().st_size > 10:
        return True
    # Partial JSONL present → not fully done; resume will continue
    return False


# ── Normalise date strings for the API ───────────────────────────────────────

def _iso(date_str: str, end_of_day: bool = False) -> str:
    if "T" in date_str:
        return date_str
    suffix = "T23:59:59Z" if end_of_day else "T00:00:00Z"
    return f"{date_str}{suffix}"


# ── Argument parsing ─────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    this_year = datetime.now(timezone.utc).year

    p = argparse.ArgumentParser(
        description="Full-history bulk ingest across all Congress.gov resources.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Year / congress range
    p.add_argument("--from-year", type=int, default=1990, metavar="YYYY",
                   help="Earliest year to ingest (default: 1990).")
    p.add_argument("--to-year", type=int, default=this_year, metavar="YYYY",
                   help=f"Latest year to ingest (default: {this_year}).")
    p.add_argument("--from-congress", type=int, default=None, metavar="N",
                   help="Override: start congress number (derived from --from-year if omitted).")
    p.add_argument("--to-congress", type=int, default=None, metavar="N",
                   help="Override: end congress number (derived from --to-year if omitted).")

    # Resource selection
    p.add_argument("--resources", default=None, metavar="r1,r2,...",
                   help="Comma-separated resource names (default: all).")
    p.add_argument("--scope",
                   choices=["date_window", "congress_scoped", "static", "all"],
                   default="all",
                   help="Restrict to resources of this scope type (default: all).")

    # Output
    p.add_argument("--outdir", default="data/full_history",
                   help="Root output directory (default: data/full_history).")

    # Item fetching
    p.add_argument("--items", action="store_true",
                   help="Fetch item-level detail for every list entry (slow).")
    p.add_argument("--max-items", type=int, default=None, metavar="N",
                   help="Cap item fetches per resource per chunk.")
    p.add_argument("--max-pages", type=int, default=None, metavar="N",
                   help="Cap list pages per resource per chunk (useful for smoke-tests).")

    # Resume
    p.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True,
                   help="Skip chunks whose output already exists (default: --resume).")

    # Delay between chunks to avoid rate-limit bursts
    p.add_argument("--chunk-delay", type=float, default=0.0, metavar="SECS",
                   help="Seconds to wait between chunks (default: 0 — rate limiter handles pacing).")

    # Concurrency
    p.add_argument("--concurrency", type=int, default=20, metavar="N",
                   help="Parallel item-fetch workers per resource (default: 20).")
    p.add_argument("--rate-limit", type=float, default=4800.0, metavar="N",
                   help="Max API requests per hour across all workers (default: 4800).")

    # Auth / misc
    p.add_argument("--api-key", default=None, help="Congress.gov API key (overrides env).")
    p.add_argument("--fail-fast", action="store_true",
                   help="Stop on first resource error inside a chunk.")
    p.add_argument("--log-level", default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    return p.parse_args()


# ── Resource selection ────────────────────────────────────────────────────────

def _select_resources(args: argparse.Namespace) -> list[Resource]:
    if args.resources:
        names = [n.strip() for n in args.resources.split(",") if n.strip()]
        out = []
        for name in names:
            try:
                out.append(Resource(name))
            except ValueError:
                valid = [r.value for r in Resource]
                print(f"ERROR: unknown resource '{name}'. Valid: {valid}", file=sys.stderr)
                sys.exit(1)
        return out

    if args.scope == "date_window":
        return [c.resource for c in date_windowed()]
    if args.scope == "congress_scoped":
        return [c.resource for c in congress_scoped()]
    if args.scope == "static":
        return [c.resource for c in static_resources()]
    return list(Resource)


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    args = _parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    outdir = Path(args.outdir)
    all_resources = _select_resources(args)

    dw_resources = [r for r in all_resources
                    if RESOURCE_CONFIGS[r].scope == "date_window"]
    cs_resources = [r for r in all_resources
                    if RESOURCE_CONFIGS[r].scope == "congress_scoped"]
    st_resources = [r for r in all_resources
                    if RESOURCE_CONFIGS[r].scope == "static"]

    from_year = args.from_year
    to_year   = args.to_year

    # Congress range (for congress-scoped resources)
    derived_congresses = _congresses_for_years(from_year, to_year)
    from_congress = args.from_congress or (derived_congresses[0] if derived_congresses else 101)
    to_congress   = args.to_congress   or (derived_congresses[-1] if derived_congresses else 119)
    congress_range = list(range(from_congress, to_congress + 1))

    total_chunks = (
        len(dw_resources) * (to_year - from_year + 1)
        + len(cs_resources) * len(congress_range)
        + len(st_resources)
    )
    logger.info(
        "Plan: %d date-windowed × %d years + %d congress-scoped × %d congresses + %d static  =  ~%d chunks",
        len(dw_resources), to_year - from_year + 1,
        len(cs_resources), len(congress_range),
        len(st_resources),
        total_chunks,
    )
    logger.info("Output root: %s", outdir.resolve())
    if args.resume:
        logger.info("Resume mode ON — completed chunks will be skipped.")

    # Shared rate limiter — one bucket across ALL workers and chunks
    rate_limiter = TokenBucket(rate_per_hour=args.rate_limit)
    logger.info(
        "Rate limiter: %.0f req/hr  |  Concurrency: %d workers",
        args.rate_limit, args.concurrency,
    )

    chunk_num   = 0
    skip_count  = 0
    fail_count  = 0

    def _make_cfg(from_date=None, to_date=None, congress=None, chunk_outdir=None):
        return PipelineConfig(
            outdir=chunk_outdir or outdir,
            from_date=from_date,
            to_date=to_date,
            congress=congress,
            fetch_items=args.items,
            save_raw_items=True,
            max_pages=args.max_pages,
            max_items=args.max_items,
            concurrency=args.concurrency,
            rate_limiter=rate_limiter,
            api_key=args.api_key,
            skip_errors=not args.fail_fast,
        )

    def _run_chunk(resources, cfg, label):
        nonlocal chunk_num, skip_count, fail_count
        chunk_num += 1

        # Resume check: skip if ALL resources in this chunk already have output
        if args.resume:
            pending = [r for r in resources if not _is_done(cfg.outdir, r, args.items)]
            if not pending:
                logger.debug("[%s] all resources already done — skipping", label)
                skip_count += len(resources)
                return
            resources = pending

        logger.info("[chunk %d] %s  (%d resources)", chunk_num, label, len(resources))
        pipeline = Pipeline(cfg)
        results = pipeline.run(resources)

        for r in results:
            if not r.success:
                fail_count += 1
                logger.error("  FAIL  %s  — %s", r.resource.value, r.error)
            else:
                logger.info("  OK    %-30s  list=%d  items=%d",
                            r.resource.value, r.list_count, r.item_count)

        if args.chunk_delay > 0:
            time.sleep(args.chunk_delay)

    # ── 1. Static resources — run once ───────────────────────────────────
    if st_resources:
        cfg = _make_cfg(chunk_outdir=outdir / "static")
        _run_chunk(st_resources, cfg, "static")

    # ── 2. Date-windowed resources — one year at a time ──────────────────
    if dw_resources:
        for year in range(from_year, to_year + 1):
            year_outdir = outdir / str(year)
            cfg = _make_cfg(
                from_date=_iso(f"{year}-01-01"),
                to_date=_iso(f"{year}-12-31", end_of_day=True),
                chunk_outdir=year_outdir,
            )
            _run_chunk(dw_resources, cfg, f"year={year}")

    # ── 3. Congress-scoped resources — one congress at a time ────────────
    if cs_resources:
        for congress in congress_range:
            cong_outdir = outdir / f"congress_{congress:03d}"
            cfg = _make_cfg(congress=congress, chunk_outdir=cong_outdir)
            _run_chunk(cs_resources, cfg, f"congress={congress}")

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"Total chunks attempted : {chunk_num}")
    print(f"Chunks skipped (resume): {skip_count}")
    print(f"Resource failures      : {fail_count}")
    print(f"Output root            : {outdir.resolve()}")
    print("=" * 60)

    sys.exit(1 if fail_count > 0 else 0)


if __name__ == "__main__":
    main()

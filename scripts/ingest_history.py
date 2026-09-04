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
With --resume (default: on), a year/congress chunk is skipped when its resource
metadata exists. Re-run with --no-resume to force a full re-fetch.

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

    # Monitor aggregate hydration progress across queued/running ingest jobs:
    uv run python scripts/monitor_ingest_progress.py
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdm.ingest import checkpoint
from cdm.ingest.pipeline import Pipeline, PipelineConfig
from cdm.ingest.resource_config import (
    RESOURCE_CONFIGS,
    congress_scoped,
    date_windowed,
    effective_scope,
    static_resources,
    validate_scope_catalog,
)
from cdm.ingest.runner import Resource
from cdm.utils.rate_limiter import TokenBucket

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

    - A successful resource metadata file is required.
    """
    meta_path = outdir / resource.value / "meta.json"
    if not meta_path.exists() or meta_path.stat().st_size < 10:
        return False
    try:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return metadata.get("resource") == resource.value and (
        not fetch_items or bool(metadata.get("fetch_items"))
    )


# ── Normalise date strings for the API ───────────────────────────────────────


def _iso(date_str: str, end_of_day: bool = False) -> str:
    if "T" in date_str:
        return date_str
    suffix = "T23:59:59Z" if end_of_day else "T00:00:00Z"
    return f"{date_str}{suffix}"


def _year_window(year: int, overlap_days: int = 0) -> tuple[str, str]:
    """Return an inclusive ISO window for a year with optional boundary overlap."""
    if overlap_days < 0:
        raise ValueError("overlap_days must be non-negative")
    start = date(year, 1, 1) - timedelta(days=overlap_days)
    end = date(year, 12, 31) + timedelta(days=overlap_days)
    return _iso(start.isoformat()), _iso(end.isoformat(), end_of_day=True)


def _write_coverage_report(outdir: Path, report: dict) -> Path:
    report_path = outdir / "coverage_report.json"
    outdir.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path


def _checkpoint_name(label: str) -> str:
    return f"history_{label.replace('=', '_')}"


def _checkpoint_parameters(cfg: PipelineConfig) -> dict:
    return {
        "from_date": cfg.from_date,
        "to_date": cfg.to_date,
        "congress": cfg.congress,
    }


def _checkpoint_matches(
    state: dict, label: str, resources: list[Resource], cfg: PipelineConfig
) -> bool:
    return (
        state.get("status") == "completed"
        and state.get("label") == label
        and state.get("resources") == [resource.value for resource in resources]
        and state.get("parameters") == _checkpoint_parameters(cfg)
    )


# ── Argument parsing ─────────────────────────────────────────────────────────


def _parse_args() -> argparse.Namespace:
    this_year = datetime.now(UTC).year
    default_from_year = max(1789, this_year - 10)

    p = argparse.ArgumentParser(
        description="Full-history bulk ingest across all Congress.gov resources.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Year / congress range
    p.add_argument(
        "--from-year",
        type=int,
        default=default_from_year,
        metavar="YYYY",
        help=f"Earliest year to ingest (default: {default_from_year}, last 10 years).",
    )
    p.add_argument(
        "--to-year",
        type=int,
        default=this_year,
        metavar="YYYY",
        help=f"Latest year to ingest (default: {this_year}).",
    )
    p.add_argument(
        "--date-overlap-days",
        type=int,
        default=0,
        metavar="N",
        help="Days to overlap adjacent yearly date windows (default: 0).",
    )
    p.add_argument(
        "--from-congress",
        type=int,
        default=None,
        metavar="N",
        help="Override: start congress number (derived from --from-year if omitted).",
    )
    p.add_argument(
        "--to-congress",
        type=int,
        default=None,
        metavar="N",
        help="Override: end congress number (derived from --to-year if omitted).",
    )

    # Resource selection
    p.add_argument(
        "--resources",
        default=None,
        metavar="r1,r2,...",
        help="Comma-separated resource names to include (default: all).",
    )
    p.add_argument(
        "--skip-resources",
        default=None,
        metavar="r1,r2,...",
        help="Comma-separated resource names to skip (e.g. 'bill' when using bulk download).",
    )
    p.add_argument(
        "--scope",
        choices=["date_window", "congress_scoped", "static", "all"],
        default="all",
        help="Restrict to resources of this scope type (default: all).",
    )

    # Output
    p.add_argument(
        "--outdir",
        default="data/full_history",
        help="Root output directory (default: data/full_history).",
    )

    # Item fetching
    p.add_argument(
        "--items",
        action="store_true",
        help="Fetch item-level detail for every list entry (slow).",
    )
    p.add_argument(
        "--max-items",
        type=int,
        default=None,
        metavar="N",
        help="Cap item fetches per resource per chunk.",
    )
    p.add_argument(
        "--max-pages",
        type=int,
        default=None,
        metavar="N",
        help="Cap list pages per resource per chunk (useful for smoke-tests).",
    )

    # Resume
    p.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip chunks whose output already exists (default: --resume).",
    )

    # Delay between chunks to avoid rate-limit bursts
    p.add_argument(
        "--chunk-delay",
        type=float,
        default=0.0,
        metavar="SECS",
        help="Seconds to wait between chunks (default: 0 — rate limiter handles pacing).",
    )

    # Concurrency
    p.add_argument(
        "--concurrency",
        type=int,
        default=20,
        metavar="N",
        help="Parallel item-fetch workers per resource (default: 20).",
    )
    p.add_argument(
        "--rate-limit",
        type=float,
        default=4800.0,
        metavar="N",
        help="Max API requests per hour across all workers (default: 4800).",
    )

    # Auth / misc
    p.add_argument(
        "--api-key", default=None, help="Congress.gov API key (overrides env)."
    )
    p.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first resource error inside a chunk.",
    )
    p.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )

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
                print(
                    f"ERROR: unknown resource '{name}'. Valid: {valid}", file=sys.stderr
                )
                sys.exit(1)
        return out

    if args.scope == "date_window":
        resources = [c.resource for c in date_windowed()]
    elif args.scope == "congress_scoped":
        resources = [c.resource for c in congress_scoped()]
    elif args.scope == "static":
        resources = [c.resource for c in static_resources()]
    else:
        resources = list(Resource)

    if args.skip_resources:
        skip_names = {n.strip() for n in args.skip_resources.split(",") if n.strip()}
        skip_set: set[Resource] = set()
        for name in skip_names:
            try:
                skip_set.add(Resource(name))
            except ValueError:
                valid = [r.value for r in Resource]
                print(
                    f"ERROR: unknown resource '{name}' in --skip-resources. Valid: {valid}",
                    file=sys.stderr,
                )
                sys.exit(1)
        resources = [r for r in resources if r not in skip_set]
        logger.info("Skipping resources: %s", ", ".join(sorted(skip_names)))

    return resources


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    args = _parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    # Suppress "Unprocessed fields" noise from the SDK — these are harmless
    # mapping gaps and would otherwise flood the log at INFO level.
    logging.getLogger("cdm.data_collection.client").setLevel(logging.ERROR)

    outdir = Path(args.outdir)
    validate_scope_catalog()
    all_resources = _select_resources(args)

    dw_resources = [
        r
        for r in all_resources
        if effective_scope(RESOURCE_CONFIGS[r]) == "date_window"
    ]
    cs_resources = [
        r
        for r in all_resources
        if effective_scope(RESOURCE_CONFIGS[r]) == "congress_scoped"
    ]
    st_resources = [
        r for r in all_resources if effective_scope(RESOURCE_CONFIGS[r]) == "static"
    ]

    from_year = args.from_year
    to_year = args.to_year
    if args.date_overlap_days < 0:
        logger.error("--date-overlap-days must be non-negative")
        sys.exit(2)

    # Congress range (for congress-scoped resources)
    derived_congresses = _congresses_for_years(from_year, to_year)
    from_congress = args.from_congress or (
        derived_congresses[0] if derived_congresses else 101
    )
    to_congress = args.to_congress or (
        derived_congresses[-1] if derived_congresses else 119
    )
    congress_range = list(range(from_congress, to_congress + 1))

    total_chunks = (
        len(dw_resources) * (to_year - from_year + 1)
        + len(cs_resources) * len(congress_range)
        + len(st_resources)
    )
    logger.info(
        "Plan: %d date-windowed × %d years + %d congress-scoped × %d congresses + %d static  =  ~%d chunks",
        len(dw_resources),
        to_year - from_year + 1,
        len(cs_resources),
        len(congress_range),
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
        args.rate_limit,
        args.concurrency,
    )

    chunk_num = 0
    skip_count = 0
    fail_count = 0
    coverage = {
        "requested": {
            "from_year": from_year,
            "to_year": to_year,
            "from_congress": from_congress,
            "to_congress": to_congress,
            "date_overlap_days": args.date_overlap_days,
            "resources": [resource.value for resource in all_resources],
        },
        "planned_chunks": total_chunks,
        "chunks": [],
    }

    def _make_cfg(from_date=None, to_date=None, congress=None, chunk_outdir=None):
        return PipelineConfig(
            outdir=chunk_outdir or outdir,
            from_date=from_date,
            to_date=to_date,
            congress=congress,
            fetch_items=args.items,
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
        planned_resources = list(resources)

        checkpoint_path_key = _checkpoint_name(label)
        checkpoint_state = checkpoint.load(checkpoint_path_key, outdir / ".checkpoints")

        # Resume check: skip if ALL resources in this chunk already have output
        if args.resume:
            pending = [r for r in resources if not _is_done(cfg.outdir, r, args.items)]
            checkpoint_matches = _checkpoint_matches(
                checkpoint_state, label, resources, cfg
            )
            if not pending and (not checkpoint_state or checkpoint_matches):
                logger.debug("[%s] all resources already done — skipping", label)
                skip_count += len(resources)
                coverage["chunks"].append({
                    "label": label,
                    "status": "skipped",
                    "resources": [r.value for r in resources],
                })
                return
            if not pending and checkpoint_state and not checkpoint_matches:
                logger.warning(
                    "[%s] existing output has a mismatched checkpoint; rerunning chunk",
                    label,
                )
            resources = pending

        logger.info("[chunk %d] %s  (%d resources)", chunk_num, label, len(resources))
        pipeline = Pipeline(cfg)
        # FatalIngestError propagates unconditionally — it stops the whole script.
        results = pipeline.run(resources)

        chunk_success = all(result.success for result in results)
        checkpoint.save(
            checkpoint_path_key,
            {
                "label": label,
                "status": "completed" if chunk_success else "failed",
                "resources": [resource.value for resource in planned_resources],
                "parameters": _checkpoint_parameters(cfg),
                "list_counts": {
                    result.resource.value: result.list_count for result in results
                },
                "item_counts": {
                    result.resource.value: result.item_count for result in results
                },
            },
            outdir / ".checkpoints",
        )

        coverage["chunks"].append({
            "label": label,
            "status": "completed",
            "resources": [
                {
                    "resource": result.resource.value,
                    "success": result.success,
                    "list_count": result.list_count,
                    "item_count": result.item_count,
                    "error": result.error,
                }
                for result in results
            ],
        })

        for r in results:
            if not r.success:
                fail_count += 1
                logger.error("  FAIL  %s  — %s", r.resource.value, r.error)
            else:
                logger.info(
                    "  OK    %-30s  list=%d  items=%d",
                    r.resource.value,
                    r.list_count,
                    r.item_count,
                )

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
            from_date, to_date = _year_window(year, args.date_overlap_days)
            cfg = _make_cfg(
                from_date=from_date,
                to_date=to_date,
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

    coverage.update({
        "attempted_chunks": chunk_num,
        "skipped_resources": skip_count,
        "resource_failures": fail_count,
    })
    report_path = _write_coverage_report(outdir, coverage)
    logger.info("Coverage report: %s", report_path)

    sys.exit(1 if fail_count > 0 else 0)


if __name__ == "__main__":
    main()

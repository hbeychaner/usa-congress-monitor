"""Queue a complete historical ingest plan through the durable job ledger."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdm.ingest.full_ingest import (
    FullIngestConfig,
    FullIngestJob,
    current_utc_date,
    plan_full_ingest,
    smoke_job,
)
from cdm.workers.tasks import submit_job


def _date(value: str) -> date:
    return date.fromisoformat(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first-congress", type=int, default=1)
    parser.add_argument("--last-congress", type=int, default=119)
    parser.add_argument("--start-date", type=_date, default=date(1789, 1, 1))
    parser.add_argument("--end-date", type=_date, default=current_utc_date())
    parser.add_argument("--window-days", type=int, default=365)
    parser.add_argument("--outdir", default="data/full_history")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--index-batch-size", type=int, default=500)
    parser.add_argument("--preserve-raw", action="store_true")
    parser.add_argument("--smoke", action="store_true", help="Queue one bounded smoke job")
    parser.add_argument("--dry-run", action="store_true", help="Print jobs without queueing")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Pause after this many dispatches (default: 50)",
    )
    parser.add_argument(
        "--batch-delay",
        type=float,
        default=2.0,
        help="Seconds to pause between batches (default: 2.0)",
    )
    return parser.parse_args()


def _config(args: argparse.Namespace) -> FullIngestConfig:
    return FullIngestConfig(
        first_congress=args.first_congress,
        last_congress=args.last_congress,
        start_date=args.start_date,
        end_date=args.end_date,
        window_days=args.window_days,
        outdir=args.outdir,
        concurrency=args.concurrency,
        index_batch_size=args.index_batch_size,
        preserve_raw=args.preserve_raw,
    )


def _print_job(job: FullIngestJob) -> None:
    print(f"{job.label}\t{job.payload}")


def main() -> None:
    args = parse_args()
    config = _config(args)
    jobs = [smoke_job(config)] if args.smoke else plan_full_ingest(config)
    if args.dry_run:
        print(f"planned_jobs={len(jobs)}")
        for job in jobs:
            _print_job(job)
        return

    # Dispatch in small batches with a pause between them so a full historical
    # backfill (potentially thousands of jobs) doesn't flood the broker in one
    # burst; the ingest worker only consumes a handful of jobs concurrently
    # anyway, so pacing dispatch costs nothing and is easy to Ctrl-C mid-run.
    for index, job in enumerate(jobs, start=1):
        record = submit_job("ingest", job.payload)
        print(f"{job.label}\t{record['id']}\t{record['status']}")
        if args.batch_size > 0 and index % args.batch_size == 0 and index < len(jobs):
            time.sleep(args.batch_delay)
    print(f"queued_jobs={len(jobs)}")


if __name__ == "__main__":
    main()

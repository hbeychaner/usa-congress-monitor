"""One-off maintenance: resend already-QUEUED jobs to Celery directly.

The routine safety net (``recover_failed_ingest_jobs``) only trickles 25
stale QUEUED jobs into the broker every 10 minutes, by design, to avoid
flooding it. That makes it impractical for clearing a large backlog of
jobs that were queued in the jobs DB but never actually dispatched (e.g.
after an interrupted ingest run). This script dispatches all of them at
once; ``JobStore.mark_running`` makes redundant dispatch a safe no-op, so
this can't create duplicate work even if some jobs were already dispatched.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdm.jobs.store import JobKind, JobStore
from cdm.workers.celery_app import celery_app
from settings import (
    CELERY_BULK_QUEUE,
    CELERY_INDEX_QUEUE,
    CELERY_INGEST_QUEUE,
    JOB_DB_PATH,
)

_TASK_AND_QUEUE = {
    JobKind.INGEST.value: ("cdm.workers.tasks.run_ingest_job", CELERY_INGEST_QUEUE),
    JobKind.INDEX.value: ("cdm.workers.tasks.run_index_job", CELERY_INDEX_QUEUE),
    JobKind.GOVINFO_BULK.value: (
        "cdm.workers.tasks.run_govinfo_bulk_job",
        CELERY_BULK_QUEUE,
    ),
    JobKind.GOVINFO_BULK_BATCH.value: (
        "cdm.workers.tasks.run_govinfo_bulk_batch",
        CELERY_BULK_QUEUE,
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--kinds",
        default="index,govinfo_bulk,govinfo_bulk_batch",
        help="Comma-separated job kinds to resume (default: %(default)s)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Dispatch this many jobs, then pause (default: %(default)s)",
    )
    parser.add_argument(
        "--batch-delay",
        type=float,
        default=1.0,
        help="Seconds to pause between batches (default: %(default)s)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Cap the total number of jobs dispatched per kind (for a test run)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be dispatched without sending anything",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    kinds = [kind.strip() for kind in args.kinds.split(",") if kind.strip()]
    unknown = [kind for kind in kinds if kind not in _TASK_AND_QUEUE]
    if unknown:
        raise SystemExit(f"Unknown job kind(s): {', '.join(unknown)}")

    store = JobStore(JOB_DB_PATH)
    total_dispatched = 0
    for kind in kinds:
        task_name, queue = _TASK_AND_QUEUE[kind]
        jobs = store.queued(kind)
        if args.limit is not None:
            jobs = jobs[: args.limit]
        print(f"{kind}: {len(jobs)} queued job(s) to dispatch to {queue!r}")
        if args.dry_run:
            continue
        for index, job in enumerate(jobs, start=1):
            celery_app.send_task(task_name, args=[job["id"]], queue=queue)
            total_dispatched += 1
            if index % args.batch_size == 0:
                print(f"  ...dispatched {index}/{len(jobs)}")
                time.sleep(args.batch_delay)
        print(f"  done: dispatched {len(jobs)} {kind} job(s)")

    if args.dry_run:
        print("Dry run: nothing was dispatched.")
    else:
        print(f"Total dispatched: {total_dispatched}")


if __name__ == "__main__":
    main()

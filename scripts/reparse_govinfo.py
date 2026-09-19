"""One-off maintenance: force re-parse of already-succeeded GovInfo packages.

Resets SUCCEEDED ``govinfo_bulk`` jobs for the selected collections back to
QUEUED and re-dispatches them to the bulk queue. The downloader's manifest
sha short-circuit means cached artifacts are NOT re-downloaded (and no rate
limit token is consumed); the parse/archive/index stages always re-run, so
this picks up parser fixes (e.g. the BILLSTATUS legislativeSubjects fix).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, update

from cdm.jobs.store import _JOBS, JobStatus, JobStore, _now
from cdm.workers.celery_app import celery_app
from settings import CELERY_BULK_QUEUE, JOB_DB_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--collections",
        default="BILLSTATUS",
        help="Comma-separated GovInfo collections to re-parse (default: %(default)s)",
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
        help="Seconds to pause between dispatch batches (default: %(default)s)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report matching jobs without requeueing or dispatching",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    collections = {c.strip().upper() for c in args.collections.split(",") if c.strip()}
    store = JobStore(JOB_DB_PATH)

    with store.engine.connect() as connection:
        rows = connection.execute(
            select(_JOBS.c.id, _JOBS.c.payload).where(
                (_JOBS.c.kind == "govinfo_bulk")
                & (_JOBS.c.status == JobStatus.SUCCEEDED.value)
            )
        ).fetchall()
    job_ids = [
        row.id
        for row in rows
        if json.loads(row.payload).get("collection", "").upper() in collections
    ]
    print(f"Matched {len(job_ids)} succeeded jobs in collections {sorted(collections)}")
    if args.dry_run or not job_ids:
        return 0

    dispatched = 0
    for start in range(0, len(job_ids), args.batch_size):
        batch = job_ids[start : start + args.batch_size]
        now = _now()
        with store._transaction_lock(), store.engine.begin() as connection:
            connection.execute(
                update(_JOBS)
                .where(
                    _JOBS.c.id.in_(batch)
                    & (_JOBS.c.status == JobStatus.SUCCEEDED.value)
                )
                .values(status=JobStatus.QUEUED.value, updated_at=now)
            )
        for job_id in batch:
            celery_app.send_task(
                "cdm.workers.tasks.run_govinfo_bulk_job",
                args=[job_id],
                queue=CELERY_BULK_QUEUE,
            )
        dispatched += len(batch)
        print(f"Requeued {dispatched}/{len(job_ids)}", flush=True)
        if start + args.batch_size < len(job_ids):
            time.sleep(args.batch_delay)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

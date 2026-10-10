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

from cdm.config import get_config
from cdm.jobs.store import _JOBS, JobStatus, JobStore, _now
from cdm.workers.celery_app import celery_app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--collections",
        default="BILLSTATUS",
        help="Comma-separated GovInfo collections to re-parse (default: %(default)s)",
    )
    parser.add_argument(
        "--congresses",
        type=int,
        nargs="*",
        help="Only re-parse jobs for these Congress numbers (default: all)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Re-parse at most this many packages (pilot runs)",
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


def _matches(payload: dict, collections: set[str], congresses: list[int] | None) -> bool:
    if payload.get("collection", "").upper() not in collections:
        return False
    return not congresses or payload.get("congress") in congresses


def main() -> int:
    args = parse_args()
    collections = {c.strip().upper() for c in args.collections.split(",") if c.strip()}
    store = JobStore(get_config().ledger.job_db_path)

    with store.engine.connect() as connection:
        rows = connection.execute(
            select(_JOBS.c.id, _JOBS.c.payload).where(
                (_JOBS.c.kind == "govinfo_bulk")
                & (_JOBS.c.status == JobStatus.SUCCEEDED.value)
            )
        ).fetchall()
    # Several jobs can exist per package; one re-parse per package is enough.
    jobs_by_package: dict[str, str] = {}
    for row in rows:
        payload = json.loads(row.payload)
        if _matches(payload, collections, args.congresses):
            jobs_by_package.setdefault(payload.get("package_id") or row.id, row.id)
    job_ids = list(jobs_by_package.values())[: args.limit]
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
                queue=get_config().queue.celery_bulk_queue,
            )
        dispatched += len(batch)
        print(f"Requeued {dispatched}/{len(job_ids)}", flush=True)
        if start + args.batch_size < len(job_ids):
            time.sleep(args.batch_delay)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

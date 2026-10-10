"""Print durable ingest and indexing job status plus coverage windows."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdm.config import get_config
from cdm.jobs.store import JobStore


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")

    store = JobStore(get_config().ledger.job_db_path)
    jobs = store.jobs()
    print(f"Jobs: {len(jobs)} total")
    for job in jobs[: args.limit]:
        print(f"  {job['id']}  {job['kind']:<6} {job['status']}")

    print("\nCoverage:")
    for row in store.coverage():
        print(
            f"  {row['resource']:<26} {row['status']:<9} "
            f"end={row['window_end'] or '-'} "
            f"discovered={row['discovered_count']:,} "
            f"hydrated={row['hydrated_count']:,}"
        )


if __name__ == "__main__":
    main()
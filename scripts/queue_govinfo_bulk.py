"""Discover and optionally queue durable GovInfo package jobs for one Congress."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdm.ingest.govinfo import GovInfoDiscovery
from cdm.jobs.store import JobKind, JobStore
from cdm.store.client import get_opensearch_client
from cdm.store.index_manager import IndexManager
from cdm.workers.tasks import submit_job
from settings import JOB_DB_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--congress", type=int, required=True)
    parser.add_argument("--outdir", default="data/full_history/govinfo")
    parser.add_argument("--queue", action="store_true")
    parser.add_argument("--staging-version", type=int, default=None)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="replace complete normalized documents instead of sparse-merging bills",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=25,
        help="package jobs per durable worker task (default: 25)",
    )
    parser.add_argument(
        "--no-batch",
        action="store_true",
        help="dispatch one Celery task per package instead of durable batches",
    )
    args = parser.parse_args()

    if args.batch_size < 1:
        parser.error("--batch-size must be positive")

    packages = GovInfoDiscovery().list_congress_packages(args.congress)
    counts = Counter(package.collection for package in packages)
    print(f"Congress {args.congress}: {len(packages)} packages")
    for collection in sorted(counts):
        print(f"  {collection}: {counts[collection]}")
    if not args.queue:
        print("Dry run: pass --queue to create durable package jobs.")
        return

    if args.staging_version is None:
        parser.error("--queue requires --staging-version")
    target_index = IndexManager(get_opensearch_client()).create_versioned(
        "legislation", args.staging_version
    )
    job_store = JobStore(JOB_DB_PATH)

    package_jobs = []
    for package in packages:
        package_jobs.append(
            submit_job(
                "govinfo_bulk",
                {
                    "collection": package.collection,
                    "congress": package.congress,
                    "measure_type": package.measure_type,
                    "package_id": package.package_id,
                    "url": package.url,
                    "session": package.session,
                    "version_code": package.version_code,
                    "outdir": args.outdir,
                    "target_index": target_index,
                    "replace": args.replace,
                },
                store=job_store,
                dispatch_existing=False,
                dispatch=args.no_batch,
            )
        )

    if args.no_batch:
        for job in package_jobs:
            print(f"{job['id']}\t{job['status']}")
        return

    for offset in range(0, len(package_jobs), args.batch_size):
        batch_jobs = package_jobs[offset : offset + args.batch_size]
        batch = submit_job(
            JobKind.GOVINFO_BULK_BATCH.value,
            {
                "job_ids": [job["id"] for job in batch_jobs],
                "batch_size": len(batch_jobs),
            },
            store=job_store,
        )
        print(f"{batch['id']}\t{batch['status']}\tpackages={len(batch_jobs)}")


if __name__ == "__main__":
    main()

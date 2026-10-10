"""Submit a durable replay of archived GovInfo records into staging."""

from __future__ import annotations

import argparse

from cdm.config import get_config
from cdm.jobs.store import JobKind
from cdm.workers.runtime import WorkerContainer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", required=True)
    parser.add_argument("--target-index", required=True)
    parser.add_argument("--report-path", required=True)
    parser.add_argument("--no-preserve-raw", action="store_true")
    args = parser.parse_args()
    job = WorkerContainer(get_config()).job_submitter.submit(
        JobKind.RECONCILE.value,
        {
            "archive_root": args.archive_root,
            "target_index": args.target_index,
            "report_path": args.report_path,
            "preserve_raw": not args.no_preserve_raw,
        },
    )
    print(f"{job['id']}\t{job['status']}")


if __name__ == "__main__":
    main()

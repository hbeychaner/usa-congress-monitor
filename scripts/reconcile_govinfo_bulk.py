"""Submit a durable replay of archived GovInfo records into staging."""

from __future__ import annotations

import argparse
from pathlib import Path

from cdm.config import get_config
from cdm.ingest.reconciliation import replay_govinfo_archives
from cdm.jobs.store import JobKind
from cdm.workers.runtime import WorkerContainer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", required=True)
    parser.add_argument("--target-index")
    parser.add_argument(
        "--archives-only",
        action="store_true",
        help="Explicitly skip Elasticsearch inspection; preview only",
    )
    parser.add_argument("--report-path", required=True)
    parser.add_argument("--no-preserve-raw", action="store_true")
    parser.add_argument(
        "--write-staging",
        action="store_true",
        help="Submit a durable write to an exact unaliased staging index; default is read-only preview",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=None,
        help="Read-only preview record limit (default: 100)",
    )
    args = parser.parse_args()
    if args.archives_only and (args.target_index or args.write_staging):
        parser.error(
            "--archives-only cannot be combined with a target or --write-staging"
        )
    if not args.archives_only and not args.target_index:
        parser.error("--target-index is required unless --archives-only is selected")
    if args.write_staging and args.max_records is not None:
        parser.error(
            "--max-records is preview-only; staging writes must not silently sample"
        )
    container = WorkerContainer(get_config())
    if not args.write_staging:
        report = replay_govinfo_archives(
            Path(args.archive_root),
            None if args.archives_only else container.elastic_client,
            target_index=args.target_index,
            report_path=Path(args.report_path),
            preserve_raw=not args.no_preserve_raw,
            preview=True,
            max_records=100 if args.max_records is None else args.max_records,
        )
        print(f"preview\t{args.report_path}\tparents={report['parent_count']}")
        return
    job = container.job_submitter.submit(
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

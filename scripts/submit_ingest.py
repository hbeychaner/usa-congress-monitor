"""Submit an idempotent ingest-and-index job to Celery."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdm.workers.tasks import submit_job


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", default="data/full_history")
    parser.add_argument("--resources", help="Comma-separated resource names")
    parser.add_argument("--from-date")
    parser.add_argument("--to-date")
    parser.add_argument("--congress", type=int)
    parser.add_argument("--fetch-items", action="store_true")
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--max-items", type=int)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--index-batch-size", type=int, default=500)
    parser.add_argument("--no-index", action="store_true")
    parser.add_argument("--preserve-raw", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = {
        "outdir": args.outdir,
        "resources": [name.strip() for name in args.resources.split(",") if name.strip()]
        if args.resources
        else None,
        "from_date": args.from_date,
        "to_date": args.to_date,
        "congress": args.congress,
        "fetch_items": args.fetch_items,
        "max_pages": args.max_pages,
        "max_items": args.max_items,
        "concurrency": args.concurrency,
        "index": not args.no_index,
        "index_batch_size": args.index_batch_size,
        "preserve_raw": args.preserve_raw,
    }
    job = submit_job("ingest", payload)
    print(f"{job['id']}\t{job['status']}")


if __name__ == "__main__":
    main()

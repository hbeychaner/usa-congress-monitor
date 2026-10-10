"""Backfill committee activities on indexed bills from archived BILLSTATUS XML."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdm.config import get_config
from cdm.ingest.committee_backfill import BillStatusFiles, CommitteeActivityBackfill
from cdm.ingest.govinfo import GovInfoBillStatusParser
from cdm.store.client import ElasticClientFactory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="Defaults to the configured archive")
    parser.add_argument("--limit", type=int, help="Process at most this many XML files")
    args = parser.parse_args()
    config = get_config()
    govinfo = config.govinfo
    if args.root:
        govinfo = govinfo.model_copy(update={"govinfo_archive_root": args.root})
    backfill = CommitteeActivityBackfill(
        ElasticClientFactory(config.elastic).create(),
        GovInfoBillStatusParser(),
        govinfo,
    )
    report = backfill.run(iter(BillStatusFiles(govinfo)), args.limit)
    print(report.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

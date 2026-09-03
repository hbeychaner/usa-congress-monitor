"""Run a bounded, all-measure-type GovInfo acquisition into staging."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdm.ingest.archive import SQLiteRecordArchive
from cdm.ingest.govinfo import (
    GovInfoBillsParser,
    GovInfoBillStatusParser,
    GovInfoBillSummaryParser,
    GovInfoDiscovery,
    GovInfoDownloader,
)
from cdm.ingest.reconciliation import replay_govinfo_archives
from cdm.store.client import get_opensearch_client
from cdm.store.index_manager import IndexManager


def _packages(discovery: GovInfoDiscovery, congress: int):
    selected = []
    for collection in ("BILLSTATUS", "BILLSUM"):
        for measure_type in discovery.MEASURE_TYPES:
            packages = discovery.list_measure_packages(
                collection, congress, measure_type
            )
            if packages:
                selected.append(packages[0])
    for measure_type in discovery.MEASURE_TYPES:
        for session in (1, 2):
            packages = discovery.list_measure_packages(
                "BILLS", congress, measure_type, session=session
            )
            if packages:
                selected.append(packages[0])
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--congress", type=int, required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--staging-version", type=int, required=True)
    args = parser.parse_args()

    root = Path(args.outdir)
    discovery = GovInfoDiscovery(timeout=60)
    downloader = GovInfoDownloader(root / "artifacts", timeout=120)
    archive_root = root / "archives"
    packages = _packages(discovery, args.congress)
    print(f"Selected {len(packages)} packages for Congress {args.congress}")

    for package in packages:
        artifact = downloader.download(package)
        if package.collection == "BILLSTATUS":
            record = GovInfoBillStatusParser().parse(artifact.read_bytes(), package)
            resource = "bill"
        elif package.collection == "BILLSUM":
            record = GovInfoBillSummaryParser().parse(artifact.read_bytes(), package)
            resource = "bill"
        else:
            record = GovInfoBillsParser().parse(artifact.read_bytes(), package)
            resource = "bill_text"
        SQLiteRecordArchive(archive_root / package.package_id, 0).write(
            resource, record, record_id=package.package_id
        )
        print(f"  archived {package.package_id}")

    target_index = IndexManager(get_opensearch_client()).create_versioned(
        "legislation", args.staging_version
    )
    report = replay_govinfo_archives(
        archive_root,
        get_opensearch_client(),
        target_index=target_index,
        report_path=root / "coverage-report.json",
    )
    print(
        f"Replayed {report['document_count']} documents into {target_index}; "
        f"quarantined {report['quarantine_count']}"
    )


if __name__ == "__main__":
    main()
"""Report discovered GovInfo package coverage against durable manifests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdm.ingest.govinfo import (
    GovInfoDiscovery,
    GovInfoManifestStore,
    summarize_govinfo_coverage,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--congress", type=int, required=True)
    parser.add_argument("--manifest-root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    packages = GovInfoDiscovery().list_congress_packages(args.congress)
    manifest_rows = []
    for path in sorted(Path(args.manifest_root).glob("**/govinfo.sqlite3")):
        manifest_rows.extend(GovInfoManifestStore(path).rows())

    report = {
        "congress": args.congress,
        "manifest_root": str(Path(args.manifest_root)),
        **summarize_govinfo_coverage(packages, manifest_rows),
    }
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["complete"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

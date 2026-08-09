"""Run ingest.fetch_and_save_all for all registered list resources.

Saves per-resource outputs to tmp_ingest/<resource>/ with the same
behavior as the CLI ingest script. Limits are configurable below.
"""

import time
from pathlib import Path

from cdm.data_collection.endpoint_registry import all_specs
from scripts.ingest import fetch_and_save_all


def main():
    out_base = Path("tmp_ingest")
    specs = all_specs()
    # collect unique resource names from specs named '<resource>_list'
    resources = sorted({name[:-5] for name in specs if name.endswith("_list")})
    print(f"Found resources: {resources}")

    # limits requested by user
    max_pages = 4
    max_items = 1000

    for r in resources:
        outdir = out_base / r
        print(f"Starting ingest for {r} -> {outdir}")
        start = time.time()
        try:
            fetch_and_save_all(
                outdir,
                resource=r,
                fetch_items=True,
                max_items=max_items,
                max_pages=max_pages,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"Ingest failed for {r}: {exc}")
        finally:
            elapsed = time.time() - start
            print(f"Finished {r} in {elapsed:.1f}s")


if __name__ == "__main__":
    main()

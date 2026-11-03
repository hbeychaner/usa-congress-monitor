"""Print a read-only analytics lineage report; never delete or submit jobs.

Run: uv run python -m scripts.preview_analytics_retirement
Only validated topic manifests are inventoried. Unreferenced runs are not
deletion candidates until replacements and live dependencies are revalidated.
"""

import argparse

from cdm.config import get_config
from cdm.container import Container


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    container = Container(get_config())
    client = container.elastic_client
    try:
        print(container.retirement_reporter.report().model_dump_json(indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    main()

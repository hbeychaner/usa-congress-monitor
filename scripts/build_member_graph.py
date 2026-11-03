"""Submit a durable member-graph build and print its job ID."""

import argparse

from cdm.config import get_config
from cdm.container import Container
from cdm.graph.models import Signal
from cdm.jobs.analytics import GraphRequest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("signals", nargs="*", type=Signal)
    request = GraphRequest(signals=parser.parse_args().signals)
    print(Container(get_config()).analytics_jobs.submit(request).model_dump_json())


if __name__ == "__main__":
    main()

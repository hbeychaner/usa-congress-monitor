"""Build member graph edges and publish the new version of each signal.

Usage:
    uv run python scripts/build_member_graph.py [--status-file PATH] [collaboration] [voting]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdm.config import get_config
from cdm.container import Container
from cdm.graph.job import GraphBuildJob
from cdm.graph.models import Signal
from cdm.graph.runner import GraphBuildRunner


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status-file", type=Path)
    parser.add_argument("signals", nargs="*", type=Signal)
    args = parser.parse_args()
    runner = GraphBuildRunner(args.status_file) if args.status_file else None
    container = Container(get_config())
    GraphBuildJob(
        container.elastic_client, container.config.elastic.analysis_index, runner
    ).run(args.signals)


if __name__ == "__main__":
    main()

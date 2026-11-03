"""Submit durable topic training/publication and print its job ID.

Capped runs and --dry-run skip model/index/cache writes and LLM calls.
The job ledger and third-party model-download caches may still be written. Published
models require a new validated full run; legacy rows are never auto-published.
Use --publish-version VERSION to switch to a previously validated complete run.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from pydantic import ValidationError

from cdm.config import get_config
from cdm.config.topic_analysis import TopicTrainingOptions
from cdm.container import Container
from cdm.jobs.analytics import TopicRequest


def parse_args(argv: Sequence[str] | None = None) -> TopicTrainingOptions:
    defaults = TopicTrainingOptions()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-docs", type=int, help="Cap the corpus; always a read-only preview"
    )
    parser.add_argument("--min-congress", type=int, default=defaults.min_congress)
    parser.add_argument("--min-topic-size", type=int, default=defaults.min_topic_size)
    parser.add_argument("--nr-bins", type=int, default=defaults.nr_bins)
    parser.add_argument("--embedding-model")
    parser.add_argument(
        "--model-dir", default=defaults.model_dir, help="Worker-visible model directory"
    )
    parser.add_argument("--no-llm-labels", action="store_true")
    parser.add_argument(
        "--dry-run", action="store_true", help="Read-only preview; no LLM calls"
    )
    parser.add_argument(
        "--publish-version", help="Publish/roll back to a validated complete run"
    )
    try:
        return TopicTrainingOptions.model_validate(vars(parser.parse_args(argv)))
    except ValidationError as exc:
        parser.error(str(exc))


def main() -> None:
    request = TopicRequest(options=parse_args())
    print(Container(get_config()).analytics_jobs.submit(request).model_dump_json())


if __name__ == "__main__":
    main()

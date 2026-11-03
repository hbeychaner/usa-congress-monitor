"""Submit a durable perspective build and print its job ID."""

import argparse

from pydantic import ValidationError

from cdm.config import get_config
from cdm.container import Container
from cdm.jobs.analytics import PerspectiveRequest


def parse_args() -> PerspectiveRequest:
    defaults = PerspectiveRequest()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--congress", dest="congresses", type=int, action="append")
    parser.add_argument("--top-topics", type=int, default=defaults.top_topics)
    parser.add_argument("--all-topics", action="store_true")
    parser.add_argument("--topic-id", dest="topic_ids", type=int, action="append")
    parser.add_argument("--no-llm-labels", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = vars(parser.parse_args())
    if args.pop("all_topics"):
        args["top_topics"] = None
    if args["congresses"] is None:
        args["congresses"] = defaults.congresses
    try:
        return PerspectiveRequest.model_validate(args)
    except ValidationError as exc:
        parser.error(str(exc))


def main() -> None:
    request = parse_args()
    print(Container(get_config()).analytics_jobs.submit(request).model_dump_json())


if __name__ == "__main__":
    main()

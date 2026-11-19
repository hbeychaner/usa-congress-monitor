"""Print read-only analytics lineage, preview cleanup, or explicitly submit cleanup.

Run: uv run python -m scripts.preview_analytics_retirement
The default report never deletes or submits jobs. --plan previews retention;
--cleanup submits a durable maintenance job that first verifies the live API.
"""

import argparse
import json
from uuid import uuid4

from cdm.config import get_config
from cdm.container import Container
from cdm.jobs.store import JobKind
from cdm.topics.cleanup import CleanupRequest
from cdm.workers.operations import OperationsContainer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="Preview exact cleanup targets")
    mode.add_argument("--cleanup", action="store_true", help="Submit verified cleanup")
    args = parser.parse_args()
    if args.plan:
        operations = OperationsContainer(get_config())
        try:
            print(operations.analytics_cleanup.plan().model_dump_json(indent=2))
        finally:
            operations.elastic_client.close()
        return
    container = Container(get_config())
    client = container.elastic_client
    try:
        if args.cleanup:
            result = container.job_submitter.submit(
                JobKind.ANALYTICS_CLEANUP,
                CleanupRequest(request_id=uuid4().hex).model_dump(mode="json"),
            )
            print(json.dumps(result))
        else:
            print(container.retirement_reporter.report().model_dump_json(indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    main()

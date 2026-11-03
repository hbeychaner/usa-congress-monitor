"""Capture/verify frozen vote repairs or rehearse them on a DIFFERENT cluster."""

import argparse
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel

from cdm.config import get_config
from cdm.graph.repair import RepairBundle
from cdm.workers.runtime import WorkerContainer


class Operation(StrEnum):
    CAPTURE = "capture"
    VERIFY = "verify"
    REHEARSE = "rehearse"


class Options(BaseModel):
    operation: Operation
    bundle: Path
    output: Path | None = None
    staging_url: str | None = None


class GraphRepairCommand:
    def run(self) -> None:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("operation", type=Operation, choices=list(Operation))
        parser.add_argument(
            "--bundle",
            type=Path,
            required=True,
            help="New capture directory, or existing sealed bundle for verify/rehearse",
        )
        parser.add_argument(
            "--output",
            type=Path,
            help="New candidate/acceptance directory (rehearse only)",
        )
        parser.add_argument(
            "--staging-url",
            help="Isolated Elasticsearch endpoint; serving cluster UUID is rejected",
        )
        options = Options.model_validate(vars(parser.parse_args()))
        if options.operation is Operation.VERIFY:
            if options.output is not None or options.staging_url is not None:
                parser.error("verify accepts only --bundle")
            print(RepairBundle(options.bundle).verify().model_dump_json(indent=2))
            return
        if options.operation is Operation.CAPTURE:
            if options.output is not None or options.staging_url is not None:
                parser.error("capture accepts only --bundle; it never writes to search")
            print(
                WorkerContainer(get_config())
                .graph_repair_capture.capture(options.bundle)
                .model_dump_json(indent=2)
            )
            return
        if options.output is None or options.staging_url is None:
            parser.error("rehearse requires --output and --staging-url")
        rehearsal = WorkerContainer(get_config()).graph_repair_rehearsal(
            options.staging_url
        )
        with rehearsal.client:
            print(
                rehearsal.run(options.bundle, options.output).model_dump_json(indent=2)
            )


if __name__ == "__main__":
    GraphRepairCommand().run()

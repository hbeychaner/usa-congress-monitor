"""Prepare/apply the approved mapping and source repair; never publish graph pointers."""

import argparse
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel

from cdm.config import get_config
from cdm.workers.runtime import WorkerContainer


class Operation(StrEnum):
    PREPARE = "prepare"
    APPLY = "apply"
    ROLLBACK = "rollback"


class Options(BaseModel):
    operation: Operation
    bundle: Path
    evidence: Path
    rehearsal: Path | None = None
    staging_url: str | None = None


class SourceRepairCommand:
    def run(self) -> None:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("operation", type=Operation, choices=list(Operation))
        parser.add_argument("--bundle", type=Path, required=True)
        parser.add_argument(
            "--evidence",
            type=Path,
            required=True,
            help="New prepared evidence directory, or existing one for apply/rollback",
        )
        parser.add_argument(
            "--rehearsal",
            type=Path,
            help="Accepted gate-one candidate directory (prepare only)",
        )
        parser.add_argument(
            "--staging-url", help="Disposable restore endpoint (prepare only)"
        )
        options = Options.model_validate(vars(parser.parse_args()))
        if options.operation is Operation.PREPARE:
            if options.rehearsal is None or options.staging_url is None:
                parser.error("prepare requires --rehearsal and --staging-url")
            repair = WorkerContainer(get_config()).graph_source_repair(
                options.staging_url
            )
            if repair.rehearsal is None:
                raise RuntimeError("Isolated restore provider is missing")
            with repair.client, repair.rehearsal.client:
                print(
                    repair.prepare(
                        options.bundle, options.rehearsal, options.evidence
                    ).model_dump_json(indent=2)
                )
            return
        if options.rehearsal is not None or options.staging_url is not None:
            parser.error("apply/rollback accept only --bundle and --evidence")
        repair = WorkerContainer(get_config()).graph_source_repair()
        with repair.client:
            result = (
                repair.apply(options.bundle, options.evidence)
                if options.operation is Operation.APPLY
                else repair.rollback(options.bundle, options.evidence)
            )
            print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    SourceRepairCommand().run()

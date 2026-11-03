"""Stage, accept real serving evidence, or CAS-publish/roll back the voting candidate."""

import argparse
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel

from cdm.config import get_config
from cdm.workers.runtime import WorkerContainer


class Operation(StrEnum):
    STAGE = "stage"
    ACCEPT = "accept"
    PUBLISH = "publish"
    ROLLBACK = "rollback"


class Options(BaseModel):
    operation: Operation
    bundle: Path
    repair_evidence: Path
    output: Path
    candidate: Path | None = None
    browser_report: Path | None = None


class VotingPromotionCommand:
    def run(self) -> None:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("operation", type=Operation, choices=list(Operation))
        parser.add_argument("--bundle", type=Path, required=True)
        parser.add_argument("--repair-evidence", type=Path, required=True)
        parser.add_argument("--output", type=Path, required=True)
        parser.add_argument(
            "--candidate", type=Path, help="Accepted candidate directory (stage only)"
        )
        parser.add_argument(
            "--browser-report",
            type=Path,
            help="Real Playwright JSON report (accept only)",
        )
        options = Options.model_validate(vars(parser.parse_args()))
        promotion = WorkerContainer(get_config()).voting_graph_promotion
        with promotion.client:
            if options.operation is Operation.STAGE:
                if options.candidate is None or options.browser_report is not None:
                    parser.error(
                        "stage requires --candidate and forbids --browser-report"
                    )
                report = promotion.stage(
                    options.bundle,
                    options.repair_evidence,
                    options.candidate,
                    options.output,
                )
            elif options.operation is Operation.ACCEPT:
                if options.browser_report is None or options.candidate is not None:
                    parser.error(
                        "accept requires --browser-report and forbids --candidate"
                    )
                report = promotion.accept(
                    options.bundle,
                    options.repair_evidence,
                    options.output,
                    options.browser_report,
                )
            else:
                if options.candidate is not None or options.browser_report is not None:
                    parser.error(
                        "publish/rollback accept only sealed --output evidence"
                    )
                report = promotion.publish(
                    options.bundle,
                    options.repair_evidence,
                    options.output,
                    rollback=options.operation is Operation.ROLLBACK,
                )
            print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    VotingPromotionCommand().run()

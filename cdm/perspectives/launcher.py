"""Starts detached perspective rebuilds for the current Congress."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from cdm.graph.runner import REPO_ROOT, GraphBuildRunner, GraphBuildStatus
from cdm.ingest.voteview import current_congress

STATUS_PATH = REPO_ROOT / "data" / "perspective_build_status.json"
LOG_PATH = REPO_ROOT / "logs" / "perspectives.log"
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_perspectives.py"


class PerspectiveBuildLauncher:
    """Runs scripts/build_perspectives.py in the background and reports its status."""

    def __init__(
        self,
        runner: GraphBuildRunner | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.runner = runner or GraphBuildRunner(STATUS_PATH, LOG_PATH, SCRIPT_PATH)
        self.now = now

    def read(self) -> GraphBuildStatus:
        return self.runner.read()

    def start(self) -> GraphBuildStatus:
        congress = current_congress(self.now().year)
        return self.runner.start(["--congress", str(congress), "--all-topics"])

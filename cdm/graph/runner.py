"""Launch and track member-graph builds that run as detached subprocesses."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from cdm.graph.models import Signal

REPO_ROOT = Path(__file__).resolve().parents[2]
STATUS_PATH = REPO_ROOT / "data" / "member_graph_status.json"
LOG_PATH = REPO_ROOT / "logs" / "member-graph.log"
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_member_graph.py"


class BuildState(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class GraphBuildStatus(BaseModel):
    state: BuildState = BuildState.IDLE
    started: bool | None = None
    pid: int | None = None
    stage: str | None = None
    message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime | None = None
    versions: dict[Signal, str] = Field(default_factory=dict)


class GraphBuildRunner:
    """Persists build status in a file so the API, workers and script share it."""

    def __init__(self, status_path: Path = STATUS_PATH, log_path: Path = LOG_PATH) -> None:
        self.status_path = status_path
        self.log_path = log_path

    @staticmethod
    def _pid_alive(pid: int | None) -> bool:
        if not pid:
            return False
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    def _load(self) -> GraphBuildStatus:
        try:
            return GraphBuildStatus.model_validate_json(self.status_path.read_text())
        except (OSError, ValueError):
            return GraphBuildStatus()

    def read(self) -> GraphBuildStatus:
        """Current status; a dead process still marked running is reported failed."""
        status = self._load()
        if status.state is BuildState.RUNNING and not self._pid_alive(status.pid):
            status.state = BuildState.FAILED
            status.message = "build process exited unexpectedly"
        return status

    def update(self, **fields: object) -> GraphBuildStatus:
        status = self._load().model_copy(
            update={**fields, "updated_at": datetime.now(UTC)}
        )
        self.status_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.status_path.with_suffix(".tmp")
        tmp.write_text(status.model_dump_json())
        tmp.replace(self.status_path)
        return status

    def start(self, signals: Sequence[Signal] = ()) -> GraphBuildStatus:
        """Start a detached build unless one is already running."""
        current = self.read()
        if current.state is BuildState.RUNNING:
            return current.model_copy(update={"started": False})
        command = [
            sys.executable,
            str(SCRIPT_PATH),
            "--status-file",
            str(self.status_path),
            *signals,
        ]
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("ab") as log:
            process = subprocess.Popen(
                command,
                cwd=REPO_ROOT,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        status = self.update(
            state=BuildState.RUNNING,
            pid=process.pid,
            started_at=datetime.now(UTC),
            finished_at=None,
            stage="starting",
            message=None,
        )
        return status.model_copy(update={"started": True})

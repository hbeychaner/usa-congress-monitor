"""Launch and track the topic-model training subprocess.

Training embeds the whole corpus and is far too heavy for a Celery task limit,
so it runs as a detached script that reports progress through a status file.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cdm.contracts.api import TopicTrainingStatus, TrainingState

REPO_ROOT = Path(__file__).resolve().parents[2]
STATUS_PATH = REPO_ROOT / "data" / "topic_training_status.json"
LOG_PATH = REPO_ROOT / "logs" / "topic-training.log"
SCRIPT_PATH = REPO_ROOT / "scripts" / "train_topic_model.py"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def read_status(path: Path = STATUS_PATH) -> TopicTrainingStatus:
    """Current training status; a dead process still marked running is failed."""
    try:
        status = TopicTrainingStatus.model_validate_json(path.read_text())
    except (OSError, ValueError):
        return TopicTrainingStatus()
    if status.state == TrainingState.RUNNING and not _pid_alive(status.pid):
        return status.model_copy(
            update={
                "state": TrainingState.FAILED,
                "message": "training process exited unexpectedly",
            }
        )
    return status


def write_status(path: Path = STATUS_PATH, **fields: Any) -> TopicTrainingStatus:
    status = read_status(path).model_copy(update={**fields, "updated_at": _now()})
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(status.model_dump_json())
    tmp.replace(path)
    return status


def start_training(*, max_docs: int | None = None) -> TopicTrainingStatus:
    """Start a detached training run unless one is already in progress."""
    current = read_status()
    if current.state == TrainingState.RUNNING:
        return current.model_copy(update={"started": False})
    command = [sys.executable, str(SCRIPT_PATH), "--status-file", str(STATUS_PATH)]
    if max_docs:
        command += ["--max-docs", str(max_docs)]
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("ab") as log:
        process = subprocess.Popen(
            command,
            cwd=REPO_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env={**os.environ, "TOKENIZERS_PARALLELISM": "false"},
        )
    status = write_status(
        state=TrainingState.RUNNING,
        pid=process.pid,
        started_at=_now(),
        finished_at=None,
        stage="starting",
        progress=0.0,
        message="",
        model_version=None,
    )
    return status.model_copy(update={"started": True})

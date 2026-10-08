"""Launch and track the topic-model training subprocess.

Training embeds the whole corpus and is far too heavy for a Celery task limit,
so it runs as a detached script that reports progress through a status file.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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


def read_status(path: Path = STATUS_PATH) -> dict[str, Any]:
    """Current training status; a dead process still marked running is failed."""
    try:
        status = json.loads(path.read_text())
    except (OSError, ValueError):
        return {"state": "idle"}
    if status.get("state") == "running" and not _pid_alive(status.get("pid")):
        status.update(state="failed", message="training process exited unexpectedly")
    return status


def write_status(path: Path = STATUS_PATH, **fields: Any) -> dict[str, Any]:
    status = {**read_status(path), **fields, "updated_at": _now()}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(status))
    tmp.replace(path)
    return status


def start_training(*, max_docs: int | None = None) -> dict[str, Any]:
    """Start a detached training run unless one is already in progress."""
    current = read_status()
    if current.get("state") == "running":
        return {**current, "started": False}
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
        state="running",
        pid=process.pid,
        started_at=_now(),
        finished_at=None,
        stage="starting",
        message="",
        model_version=None,
    )
    return {**status, "started": True}

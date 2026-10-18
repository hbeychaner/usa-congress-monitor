import os
import time
from datetime import UTC, datetime
from pathlib import Path

from cdm.graph.runner import BuildState, GraphBuildRunner
from cdm.perspectives.launcher import PerspectiveBuildLauncher


def test_start_does_not_launch_second_build(tmp_path: Path) -> None:
    runner = GraphBuildRunner(tmp_path / "status.json", tmp_path / "log")
    runner.update(state=BuildState.RUNNING, pid=os.getpid())
    launcher = PerspectiveBuildLauncher(
        runner, now=lambda: datetime(2026, 10, 19, tzinfo=UTC)
    )
    assert launcher.start().started is False


def test_start_passes_current_congress_to_the_script(tmp_path: Path) -> None:
    script = tmp_path / "echo_args.py"
    out = tmp_path / "args.txt"
    script.write_text(
        f"import sys, pathlib; pathlib.Path({str(out)!r}).write_text(' '.join(sys.argv[1:]))"
    )
    runner = GraphBuildRunner(tmp_path / "status.json", tmp_path / "log", script)
    launcher = PerspectiveBuildLauncher(
        runner, now=lambda: datetime(2026, 10, 19, tzinfo=UTC)
    )
    assert launcher.start().started is True
    for _ in range(100):
        if out.exists() and out.read_text():
            break
        time.sleep(0.05)
    assert out.read_text().endswith("--congress 119 --all-topics")

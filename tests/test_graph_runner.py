from pathlib import Path

from cdm.graph.models import Signal
from cdm.graph.runner import BuildState, GraphBuildRunner


def test_missing_status_file_is_idle(tmp_path: Path):
    assert GraphBuildRunner(tmp_path / "status.json").read().state is BuildState.IDLE


def test_update_persists_and_dead_running_process_is_failed(tmp_path: Path):
    runner = GraphBuildRunner(tmp_path / "status.json")
    runner.update(state=BuildState.RUNNING, pid=2**22 + 12345, versions={Signal.VOTING: "v1"})
    status = runner.read()
    assert status.state is BuildState.FAILED
    assert status.versions == {Signal.VOTING: "v1"}


def test_start_does_not_launch_second_build(tmp_path: Path):
    import os

    runner = GraphBuildRunner(tmp_path / "status.json")
    runner.update(state=BuildState.RUNNING, pid=os.getpid())
    assert runner.start().started is False

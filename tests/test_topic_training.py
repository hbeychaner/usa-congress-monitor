import json

from cdm.contracts.api import TopicTrainingStatus, TrainingState
from cdm.utils import topic_training


def test_dead_pid_marks_running_status_failed(tmp_path):
    path = tmp_path / "status.json"
    path.write_text(json.dumps({"state": "running", "pid": 2**22 - 3}))
    assert topic_training.read_status(path).state == TrainingState.FAILED


def test_start_training_refuses_second_run(monkeypatch):
    monkeypatch.setattr(
        topic_training, "read_status", lambda *a, **k: TopicTrainingStatus(state=TrainingState.RUNNING, pid=1)
    )
    result = topic_training.start_training()
    assert result.started is False


def test_missing_status_is_idle(tmp_path):
    assert topic_training.read_status(tmp_path / "none.json") == TopicTrainingStatus()

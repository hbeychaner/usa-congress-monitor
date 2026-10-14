import threading
from pathlib import Path

from cdm.jobs.store import JobKind, JobStatus, JobStore
from cdm.workers.heartbeat import JobHeartbeat


def _running_job(tmp_path: Path) -> tuple[JobStore, str]:
    store = JobStore(tmp_path / "jobs.sqlite3", repair=False)
    job = store.create(JobKind.INDEX.value, "key", {})
    store.mark_running(job["id"])
    return store, job["id"]


def test_touch_refreshes_only_running_jobs(tmp_path: Path) -> None:
    store, job_id = _running_job(tmp_path)
    before = store.get(job_id)["updated_at"]

    store.touch(job_id)

    assert store.get(job_id)["updated_at"] > before
    store.mark_succeeded(job_id)
    finished = store.get(job_id)["updated_at"]
    store.touch(job_id)
    assert store.get(job_id)["updated_at"] == finished


def test_heartbeat_keeps_running_job_out_of_stale_set(tmp_path: Path) -> None:
    store, job_id = _running_job(tmp_path)
    beat = threading.Event()
    original = store.touch

    def touch(target: str) -> None:
        original(target)
        beat.set()

    store.touch = touch  # type: ignore[method-assign]
    with JobHeartbeat(store, 0.01).watch(job_id):
        assert beat.wait(5)
        refreshed = store.get(job_id)["updated_at"]
        assert store.stale_active(refreshed) == []
    assert store.get(job_id)["status"] == JobStatus.RUNNING.value


def test_heartbeat_stops_after_watch_exits(tmp_path: Path) -> None:
    store, job_id = _running_job(tmp_path)
    calls: list[str] = []
    store.touch = calls.append  # type: ignore[method-assign]
    heartbeat = JobHeartbeat(store, 0.01)

    with heartbeat.watch(job_id):
        pass
    settled = len(calls)
    threading.Event().wait(0.05)

    assert len(calls) == settled

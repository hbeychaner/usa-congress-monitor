from typing import Any, cast

from cdm.jobs.store import JobKind, JobStatus
from cdm.workers import tasks


class FakeLock:
    def __init__(self, acquired):
        self.acquired = acquired
        self.released = False

    def acquire(self):
        return self.acquired

    def release(self):
        self.released = True


class FakeRedis:
    def __init__(self, lock):
        self.lock_instance = lock

    def lock(self, name, *, timeout, blocking):
        assert name == "congress:workers:recover_failed_ingest_jobs"
        assert timeout == 3600
        assert blocking is False
        return self.lock_instance


class FakeStore:
    def __init__(self):
        self.requeued = []

    def failed(self):
        return []

    def jobs(self, kind=None):
        return []

    def requeue(self, job_id):
        self.requeued.append(job_id)
        return {
            "id": job_id,
            "kind": JobKind.GOVINFO_BULK.value,
            "status": JobStatus.QUEUED.value,
        }


def test_recovery_skips_when_another_sweep_holds_lock(monkeypatch):
    lock = FakeLock(acquired=False)
    monkeypatch.setattr(tasks, "_redis", lambda: FakeRedis(lock))

    result = cast(Any, tasks.recover_failed_ingest_jobs).run()

    assert result == {"recovered": [], "skipped": "already_running"}
    assert lock.released is False


def test_recovery_releases_lock_after_sweep(monkeypatch):
    lock = FakeLock(acquired=True)
    store = FakeStore()
    dispatched = []
    monkeypatch.setattr(tasks, "_redis", lambda: FakeRedis(lock))
    monkeypatch.setattr(tasks, "_store", lambda: store)
    monkeypatch.setattr(
        tasks.celery_app,
        "send_task",
        lambda name, *, args, queue: dispatched.append((name, args, queue)),
    )

    result = cast(Any, tasks.recover_failed_ingest_jobs).run()

    assert result == {"recovered": []}
    assert lock.released is True
    assert store.requeued == []
    assert dispatched == []

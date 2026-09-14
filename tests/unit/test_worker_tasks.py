from datetime import UTC, datetime, timedelta
from typing import Any, cast

from cdm.jobs.store import JobKind, JobStatus
from cdm.workers import tasks


def test_denormalized_summaries_are_not_queued_for_direct_indexing():
    assert not tasks._should_queue_index_job("summaries")
    assert tasks._should_queue_index_job("bill")


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
    def __init__(self, jobs=None, queued=None, active=None):
        self.requeued = []
        self._jobs = jobs or []
        self._queued = queued or []
        self._active = active or []

    def failed(self):
        return []

    def stale_active(self, cutoff):
        return self._active

    def stale_queued(self, kinds, cutoff, limit):
        return [job for job in self._queued if job["kind"] in kinds][:limit]

    def jobs(self, kind=None):
        return [job for job in self._jobs if kind is None or job["kind"] == kind]

    def requeue(self, job_id):
        self.requeued.append(job_id)
        job = next(
            (job for job in (*self._jobs, *self._queued) if job["id"] == job_id),
            None,
        )
        return {
            "id": job_id,
            "kind": job["kind"] if job else JobKind.GOVINFO_BULK.value,
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


def test_recovery_requeues_stale_queued_govinfo_package(monkeypatch):
    lock = FakeLock(acquired=True)
    job = {
        "id": "govinfo_bulk:stale",
        "kind": JobKind.GOVINFO_BULK.value,
        "status": JobStatus.QUEUED.value,
        "updated_at": (datetime.now(UTC) - timedelta(minutes=90)).isoformat(),
        "payload": {},
    }
    store = FakeStore(queued=[job])
    dispatched = []
    monkeypatch.setattr(tasks, "_redis", lambda: FakeRedis(lock))
    monkeypatch.setattr(tasks, "_store", lambda: store)
    monkeypatch.setattr(
        tasks.celery_app,
        "send_task",
        lambda name, *, args, queue: dispatched.append((name, args, queue)),
    )

    result = cast(Any, tasks.recover_failed_ingest_jobs).run()

    assert result == {"recovered": [job["id"]]}
    assert store.requeued == [job["id"]]
    assert dispatched == [
        (
            "cdm.workers.tasks.run_govinfo_bulk_job",
            [job["id"]],
            tasks.CELERY_INGEST_QUEUE,
        )
    ]


def test_recovery_requeues_stale_queued_ingest_job(monkeypatch):
    lock = FakeLock(acquired=True)
    job = {
        "id": "ingest:stale-queued",
        "kind": JobKind.INGEST.value,
        "status": JobStatus.QUEUED.value,
        "updated_at": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
        "payload": {},
    }
    store = FakeStore(queued=[job])
    dispatched = []
    monkeypatch.setattr(tasks, "_redis", lambda: FakeRedis(lock))
    monkeypatch.setattr(tasks, "_store", lambda: store)
    monkeypatch.setattr(
        tasks.celery_app,
        "send_task",
        lambda name, *, args, queue: dispatched.append((name, args, queue)),
    )

    result = cast(Any, tasks.recover_failed_ingest_jobs).run()

    assert result == {"recovered": [job["id"]]}
    assert dispatched == [
        (
            "cdm.workers.tasks.run_ingest_job",
            [job["id"]],
            tasks.CELERY_INGEST_QUEUE,
        )
    ]


def test_recovery_caps_orphaned_queued_jobs_per_tick(monkeypatch):
    lock = FakeLock(acquired=True)
    stale = (datetime.now(UTC) - timedelta(minutes=90)).isoformat()
    jobs = [
        {
            "id": f"index:{i}",
            "kind": JobKind.INDEX.value,
            "status": JobStatus.QUEUED.value,
            "updated_at": stale,
            "payload": {},
        }
        for i in range(tasks._ORPHAN_RECOVERY_BATCH_LIMIT + 10)
    ]
    store = FakeStore(queued=jobs)
    dispatched = []
    monkeypatch.setattr(tasks, "_redis", lambda: FakeRedis(lock))
    monkeypatch.setattr(tasks, "_store", lambda: store)
    monkeypatch.setattr(
        tasks.celery_app,
        "send_task",
        lambda name, *, args, queue: dispatched.append((name, args, queue)),
    )

    result = cast(Any, tasks.recover_failed_ingest_jobs).run()

    assert len(result["recovered"]) == tasks._ORPHAN_RECOVERY_BATCH_LIMIT
    assert len(dispatched) == tasks._ORPHAN_RECOVERY_BATCH_LIMIT


def test_recovery_requeues_stale_active_job(monkeypatch):
    lock = FakeLock(acquired=True)
    job = {
        "id": "ingest:stale-running",
        "kind": JobKind.INGEST.value,
        "status": JobStatus.RUNNING.value,
        "payload": {},
    }
    store = FakeStore(active=[job])
    dispatched = []
    monkeypatch.setattr(tasks, "_redis", lambda: FakeRedis(lock))
    monkeypatch.setattr(tasks, "_store", lambda: store)
    monkeypatch.setattr(
        tasks.celery_app,
        "send_task",
        lambda name, *, args, queue: dispatched.append((name, args, queue)),
    )

    result = cast(Any, tasks.recover_failed_ingest_jobs).run()

    assert result == {"recovered": [job["id"]]}
    assert dispatched == [
        (
            "cdm.workers.tasks.run_ingest_job",
            [job["id"]],
            tasks.CELERY_INGEST_QUEUE,
        )
    ]


def test_govinfo_batch_fans_out_package_jobs(monkeypatch):
    package_ids = ["govinfo_bulk:one", "govinfo_bulk:two"]

    class BatchStore:
        def __init__(self):
            self.succeeded = []

        def mark_running(self, job_id):
            assert job_id == "govinfo_bulk_batch:one"
            return {
                "id": job_id,
                "payload": {"job_ids": package_ids},
            }

        def mark_succeeded(self, job_id):
            self.succeeded.append(job_id)

    store = BatchStore()
    dispatched = []
    monkeypatch.setattr(tasks, "_store", lambda: store)
    monkeypatch.setattr(
        tasks.celery_app,
        "send_task",
        lambda name, *, args, queue: dispatched.append((name, args, queue)),
    )

    result = cast(Any, tasks.run_govinfo_bulk_batch).run(
        "govinfo_bulk_batch:one"
    )

    assert result == {
        "job_id": "govinfo_bulk_batch:one",
        "packages_dispatched": package_ids,
    }
    assert store.succeeded == ["govinfo_bulk_batch:one"]
    assert dispatched == [
        (
            "cdm.workers.tasks.run_govinfo_bulk_job",
            [package_id],
            tasks.CELERY_INGEST_QUEUE,
        )
        for package_id in package_ids
    ]

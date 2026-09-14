from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from cdm.jobs.store import JobKind, JobStatus
from cdm.workers import tasks


def test_denormalized_summaries_are_not_queued_for_direct_indexing():
    assert not tasks._should_queue_index_job("summaries")
    assert tasks._should_queue_index_job("bill")


def test_soft_time_limit_failures_are_retryable():
    assert tasks._is_retryable_error("SoftTimeLimitExceeded()")
    assert not tasks._is_retryable_error("ValueError: bad payload")


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


def test_stream_source_job_id_handles_colons_in_job_ids():
    assert (
        tasks._stream_source_job_id(
            "congress:ingest:manual-recovery:historical-bill:congress-116:20260907-v1:bill"
        )
        == "manual-recovery:historical-bill:congress-116:20260907-v1"
    )
    assert (
        tasks._stream_source_job_id("congress:ingest:govinfo_bulk:abc123:bill_text")
        == "govinfo_bulk:abc123"
    )
    assert tasks._stream_source_job_id("other:prefix:x") is None


class FakeRetentionRedis:
    def __init__(self, streams):
        self.streams = set(streams)
        self.deleted = []

    def scan_iter(self, match=None, count=None):
        yield from [name.encode() for name in sorted(self.streams)]

    def delete(self, key):
        name = key.decode() if isinstance(key, bytes) else key
        self.streams.discard(name)
        self.deleted.append(name)


def _backdate(store, job_id, timestamp):
    from sqlalchemy import update

    from cdm.jobs.store import _JOBS

    with store.engine.begin() as connection:
        connection.execute(
            update(_JOBS).where(_JOBS.c.id == job_id).values(updated_at=timestamp)
        )


def test_retention_prunes_old_terminal_jobs_and_artifacts(tmp_path, monkeypatch):
    from cdm.jobs.store import JobStore

    monkeypatch.chdir(tmp_path)
    store = JobStore(tmp_path / "data" / "jobs.sqlite3")
    old = (datetime.now(UTC) - timedelta(days=45)).isoformat()

    aged = store.create(
        "ingest", "ingest:aged", {"resources": ["bill"], "outdir": "data/daily"}
    )
    store.mark_running(aged["id"])
    store.mark_succeeded(aged["id"])
    _backdate(store, aged["id"], old)
    archive_dir = tmp_path / "data" / "daily" / aged["id"]
    archive_dir.mkdir(parents=True)
    (archive_dir / "records.sqlite3").write_bytes(b"x")

    recent = store.create("ingest", "ingest:recent", {"outdir": "data/daily"})
    store.mark_running(recent["id"])
    store.mark_succeeded(recent["id"])

    failed = store.create("ingest", "ingest:failed", {"outdir": "data/daily"})
    store.mark_running(failed["id"])
    store.mark_failed(failed["id"], "boom")
    _backdate(store, failed["id"], old)

    redis = FakeRetentionRedis([
        f"congress:ingest:{aged['id']}:bill",
        f"congress:ingest:{recent['id']}:bill",
        "congress:ingest:ghost-job:bill",
    ])
    monkeypatch.setattr(tasks, "_store", lambda: store)
    monkeypatch.setattr(tasks, "_redis", lambda: redis)

    result = cast(Any, tasks.run_retention_maintenance).run()

    assert result["pruned_jobs"] == 1
    assert result["archives_deleted"] == 1
    assert not archive_dir.exists()
    # Pruned job stream and the orphaned ghost stream are removed; the
    # recent job's stream is kept.
    assert sorted(redis.deleted) == sorted([
        f"congress:ingest:{aged['id']}:bill",
        "congress:ingest:ghost-job:bill",
    ])
    with pytest.raises(KeyError):
        store.get(aged["id"])
    assert store.get(recent["id"])["status"] == "succeeded"
    assert store.get(failed["id"])["status"] == "failed"
    # Coverage history survives pruning.
    assert any(row["job_id"] == aged["id"] for row in store.coverage("bill"))


def test_retention_protects_jobs_referenced_by_unfinished_index_jobs(
    tmp_path, monkeypatch
):
    from cdm.jobs.store import JobStore

    monkeypatch.chdir(tmp_path)
    store = JobStore(tmp_path / "data" / "jobs.sqlite3")
    old = (datetime.now(UTC) - timedelta(days=45)).isoformat()

    source = store.create("ingest", "ingest:source", {"outdir": "data/daily"})
    store.mark_running(source["id"])
    store.mark_succeeded(source["id"])
    _backdate(store, source["id"], old)

    index_job = store.create(
        "index",
        "index:pending",
        {"stream": f"congress:ingest:{source['id']}:bill", "resource": "bill"},
    )
    store.mark_running(index_job["id"])
    store.mark_failed(index_job["id"], "Indexed 0 records, expected 10")

    redis = FakeRetentionRedis([f"congress:ingest:{source['id']}:bill"])
    monkeypatch.setattr(tasks, "_store", lambda: store)
    monkeypatch.setattr(tasks, "_redis", lambda: redis)

    result = cast(Any, tasks.run_retention_maintenance).run()

    assert result["pruned_jobs"] == 0
    assert redis.deleted == []
    assert store.get(source["id"])["status"] == "succeeded"


def test_index_job_archive_fallback_replays_missing_stream(tmp_path, monkeypatch):
    from cdm.ingest.archive import SQLiteRecordArchive

    archive = SQLiteRecordArchive(tmp_path, 0)
    archive.write("bill", {"id": "bill:119:hr:1", "title": "One"})
    archive.write("bill", {"id": "bill:119:hr:2", "title": "Two"})

    upserts = []
    monkeypatch.setattr(
        "cdm.store.indexer.to_document",
        lambda record, resource, preserve_raw=False, ingest_metadata=None: record,
    )
    monkeypatch.setattr(
        "cdm.store.mapping_validation.validate_document", lambda doc, resource: None
    )

    def fake_bulk_upsert(client, resource, documents, target_index=None, replace=False):
        upserts.extend(documents)
        return {"updated": len(documents), "errors": False}

    monkeypatch.setattr("cdm.store.opensearch.bulk_upsert", fake_bulk_upsert)

    payload = {
        "resource": "bill",
        "archive_root": str(tmp_path),
        "batch_size": 1,
        "stream": "congress:ingest:job:bill",
    }
    replayed = tasks._replay_archive_into_index(object(), payload)

    assert replayed == 2
    assert {doc["id"] for doc in upserts} == {"bill:119:hr:1", "bill:119:hr:2"}


def test_index_job_archive_fallback_skips_when_archive_missing(tmp_path):
    payload = {"resource": "bill", "archive_root": str(tmp_path / "nope")}
    assert tasks._replay_archive_into_index(object(), payload) == 0
    assert tasks._replay_archive_into_index(object(), {"resource": "bill"}) == 0

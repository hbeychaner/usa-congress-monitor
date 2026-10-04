from cdm.jobs.store import JobKind, JobStatus, JobStore


def test_claim_queued_claims_matching_jobs_once(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3", repair=False)
    for index in range(4):
        store.create(
            JobKind.INDEX.value,
            f"key-{index}",
            {"resource": "bill" if index < 3 else "law"},
        )

    claimed = store.claim_queued(
        JobKind.INDEX.value, lambda job: job["payload"]["resource"] == "bill", 2
    )

    assert len(claimed) == 2
    assert {store.get(job["id"])["status"] for job in claimed} == {
        JobStatus.RUNNING.value
    }
    again = store.claim_queued(
        JobKind.INDEX.value, lambda job: job["payload"]["resource"] == "bill", 10
    )
    assert len(again) == 1
    assert store.claim_queued(JobKind.INDEX.value, lambda job: True, 0) == []


def test_repair_flag_skips_window_reconciliation(tmp_path):
    path = tmp_path / "jobs.sqlite3"
    JobStore(path, repair=False)
    store = JobStore(path, repair=False)
    store.repair_legacy_windows()
    assert store.jobs() == []

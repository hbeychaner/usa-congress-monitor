from cdm.jobs.store import JobStore


def test_job_store_is_idempotent_and_tracks_lifecycle(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    first = store.create("index", "index:one", {"resource": "bill"})
    second = store.create("index", "index:one", {"resource": "bill", "changed": True})

    assert first["id"] == second["id"]
    assert second["payload"] == {"resource": "bill"}
    assert second["status"] == "queued"

    store.mark_running(first["id"])
    running = store.get(first["id"])
    assert running["status"] == "running"
    assert running["attempts"] == 1

    store.mark_succeeded(first["id"])
    assert store.get(first["id"])["status"] == "succeeded"

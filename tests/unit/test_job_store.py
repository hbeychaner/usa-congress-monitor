from concurrent.futures import ThreadPoolExecutor

from cdm.ingest.govinfo import GovInfoPackage
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


def test_job_store_tracks_retrying_state(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    job = store.create("ingest", "ingest:one", {"resource": "bill"})

    store.mark_running(job["id"])
    retrying = store.mark_retrying(job["id"], "server error: 500")

    assert retrying["status"] == "retrying"
    assert retrying["last_error"] == "server error: 500"

    resumed = store.mark_running(job["id"])
    assert resumed["status"] == "running"
    assert resumed["attempts"] == 2


def test_job_store_requeues_failed_job(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    job = store.create("ingest", "ingest:two", {"resource": "bill"})
    store.mark_failed(job["id"], "server error: 500")

    requeued = store.requeue(job["id"])

    assert requeued["status"] == "queued"


def test_job_store_lists_jobs_newest_first(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    store.create("index", "index:one", {"resource": "bill"})
    store.create("index", "index:two", {"resource": "member"})

    jobs = store.jobs()

    assert [job["id"] for job in jobs] == ["index:two", "index:one"]


def test_job_store_registers_govinfo_package_idempotently(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    package = GovInfoPackage(
        package_id="BILLSTATUS-118HR1",
        collection="BILLSTATUS",
        congress=118,
        measure_type="hr",
        url="https://example.test/status.xml",
    )

    first = store.create_govinfo_bulk_job(package, outdir=tmp_path / "archive")
    second = store.create_govinfo_bulk_job(package, outdir=tmp_path / "other")

    assert first["id"] == second["id"]
    assert first["kind"] == "govinfo_bulk"
    assert first["payload"]["package_id"] == "BILLSTATUS-118HR1"
    assert second["payload"]["outdir"] == str(tmp_path / "archive")


def test_job_store_can_initialize_concurrently(tmp_path):
    path = tmp_path / "jobs.sqlite3"

    def initialize_store(index):
        store = JobStore(path)
        return store.create("index", f"index:{index}", {"resource": "bill"})["id"]

    with ThreadPoolExecutor(max_workers=4) as executor:
        ids = list(executor.map(initialize_store, range(4)))

    assert ids == ["index:0", "index:1", "index:2", "index:3"]

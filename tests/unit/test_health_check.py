from datetime import UTC, datetime, timedelta
from typing import Any, cast

from scripts.health_check import _failure_category, _job_snapshot


def test_failure_category_keeps_vendor_errors_out_of_retry_bucket():
    assert _failure_category("400 Client Error: Bad Request") == "vendor_4xx"
    assert _failure_category("HTTPSConnectionPool: Read timed out") == "transient"


class FakeStore:
    def __init__(self, jobs):
        self._jobs = jobs

    def jobs(self):
        return self._jobs


def test_job_snapshot_accepts_naive_sqlite_timestamps():
    now = datetime.now(UTC)
    jobs = [
        {
            "id": "index:one",
            "kind": "index",
            "status": "succeeded",
            "updated_at": (now - timedelta(minutes=1)).replace(tzinfo=None).isoformat(),
            "finished_at": now.replace(tzinfo=None).isoformat(),
        }
    ]

    snapshot = _job_snapshot(cast(Any, FakeStore(jobs)), window_minutes=15)

    assert snapshot["recent_updates"] == 1
    assert snapshot["recent_succeeded"] == 1
    assert snapshot["latest_finished_at"] == jobs[0]["finished_at"]

from datetime import UTC, datetime
from types import SimpleNamespace

from cdm.jobs.store import JobStatus
from cdm.workers import tasks


class FakeStore:
    def __init__(self, rows):
        self.rows = rows

    def coverage(self, resource):
        return self.rows.get(resource, [])


def test_coverage_gap_payloads_only_returns_stale_resources(monkeypatch):
    now = datetime(2026, 8, 25, 12, tzinfo=UTC)
    monkeypatch.setattr(
        tasks,
        "_store",
        lambda: FakeStore(
            {
                "bill": [
                    {
                        "status": JobStatus.SUCCEEDED.value,
                        "window_end": "2026-08-23T11:59:59Z",
                    }
                ],
                "member": [
                    {
                        "status": JobStatus.SUCCEEDED.value,
                        "window_end": "2026-08-25T01:00:00Z",
                    }
                ],
            }
        ),
    )
    monkeypatch.setattr(
        tasks,
        "date_windowed",
        lambda: [
            SimpleNamespace(
                resource=SimpleNamespace(value="bill"), fetch_items_default=False
            ),
            SimpleNamespace(
                resource=SimpleNamespace(value="member"), fetch_items_default=False
            ),
        ],
    )

    payloads = tasks.coverage_gap_payloads(now)

    assert payloads == [
        {
            "outdir": "data/daily",
            "resources": ["bill"],
            "from_date": "2026-08-23T11:59:59Z",
            "to_date": "2026-08-25T12:00:00Z",
            "fetch_items": False,
            "index": True,
            "concurrency": 4,
            "index_batch_size": 500,
            "mode": "coverage_gap",
        }
    ]


def test_coverage_gap_payloads_ignore_incomplete_windows(monkeypatch):
    now = datetime(2026, 8, 25, 12, tzinfo=UTC)
    monkeypatch.setattr(
        tasks,
        "_store",
        lambda: FakeStore(
            {
                "bill": [
                    {
                        "status": JobStatus.RUNNING.value,
                        "window_end": "2026-08-20T00:00:00Z",
                    }
                ]
            }
        ),
    )
    monkeypatch.setattr(
        tasks,
        "date_windowed",
        lambda: [
            SimpleNamespace(
                resource=SimpleNamespace(value="bill"), fetch_items_default=True
            )
        ],
    )

    assert tasks.coverage_gap_payloads(now) == []
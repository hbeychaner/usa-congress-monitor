"""Report dependency, queue, throughput, and failure health for local operations."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdm.jobs.store import JobStore
from cdm.store.client import get_opensearch_client
from cdm.workers.celery_app import celery_app
from settings import JOB_DB_PATH, REDIS_URL


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def _failure_category(error: str | None) -> str:
    text = (error or "").lower()
    if any(marker in text for marker in (
        "timeout",
        "connection",
        "database is locked",
        "server error: 5",
        "http 5",
        "429",
    )):
        return "transient"
    if "400 client error" in text or "bad request" in text:
        return "vendor_4xx"
    if any(marker in text for marker in ("validation error", "parse", "xml")):
        return "malformed_or_validation"
    if "quarantined" in text or "superseded" in text:
        return "manual_review"
    return "unclassified"


def _job_snapshot(store: JobStore, window_minutes: int) -> dict[str, Any]:
    jobs = store.jobs()
    cutoff = datetime.now(UTC) - timedelta(minutes=window_minutes)
    counts = Counter((job["kind"], job["status"]) for job in jobs)
    recent = [
        job
        for job in jobs
        if _parse_timestamp(job["updated_at"]) >= cutoff
    ]
    failures = Counter(
        (job["kind"], _failure_category(job.get("last_error")))
        for job in jobs
        if job["status"] == "failed"
    )
    latest_finished = max(
        (
            job["finished_at"]
            for job in jobs
            if job.get("finished_at")
        ),
        default=None,
    )
    return {
        "status": "ok",
        "integrity": "ok",
        "total": len(jobs),
        "counts": {
            f"{kind}:{status}": count
            for (kind, status), count in sorted(counts.items())
        },
        "recent_updates": len(recent),
        "recent_succeeded": sum(
            1
            for job in recent
            if job["status"] == "succeeded"
        ),
        "latest_finished_at": latest_finished,
        "failures": [
            {"kind": kind, "category": category, "count": count}
            for (kind, category), count in failures.most_common(20)
        ],
    }


def _check_redis() -> dict[str, Any]:
    from redis import Redis

    client = Redis.from_url(REDIS_URL)
    client.ping()
    return {"status": "ok"}


def _check_opensearch() -> dict[str, Any]:
    client = get_opensearch_client()
    health = client.cluster.health()
    return {
        "status": "ok",
        "cluster": health.get("cluster_name"),
        "health": health.get("status"),
        "number_of_nodes": health.get("number_of_nodes"),
    }


def _check_celery() -> dict[str, Any]:
    inspector = celery_app.control.inspect(timeout=3)
    ping = inspector.ping() or {}
    stats = inspector.stats() or {}
    workers = sorted(set(ping) | set(stats))
    return {
        "status": "ok" if workers else "failed",
        "workers": workers,
        "worker_count": len(workers),
    }


def collect_health(window_minutes: int = 15) -> dict[str, Any]:
    """Collect health data without changing application state."""
    report: dict[str, Any] = {
        "checked_at": datetime.now(UTC).isoformat(),
        "status": "ok",
        "warnings": [],
        "checks": {},
    }

    try:
        with sqlite3.connect(JOB_DB_PATH) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {integrity}")
        report["checks"]["jobs"] = _job_snapshot(JobStore(JOB_DB_PATH), window_minutes)
    except Exception as exc:  # noqa: BLE001 - report dependency failures without aborting the check.
        report["status"] = "failed"
        report["checks"]["jobs"] = {"status": "failed", "error": str(exc)}

    for name, check in (("celery", _check_celery), ("redis", _check_redis), ("opensearch", _check_opensearch)):
        try:
            report["checks"][name] = check()
        except Exception as exc:  # noqa: BLE001 - report dependency failures without aborting the check.
            report["status"] = "failed"
            report["checks"][name] = {"status": "failed", "error": str(exc)}

    jobs = report["checks"].get("jobs", {})
    counts = jobs.get("counts", {})
    backlog = sum(
        count
        for key, count in counts.items()
        if key.endswith(":queued")
    )
    if backlog:
        report["warnings"].append(f"{backlog:,} queued jobs remain")
    if jobs.get("failures"):
        report["warnings"].append(
            f"{sum(item['count'] for item in jobs['failures']):,} failed jobs remain"
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-minutes", type=int, default=15)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()
    if args.window_minutes < 1:
        parser.error("--window-minutes must be positive")

    report = collect_health(args.window_minutes)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Health: {report['status']}")
        for name, check in report["checks"].items():
            print(f"  {name}: {check['status']}")
        for warning in report["warnings"]:
            print(f"Warning: {warning}")
    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())

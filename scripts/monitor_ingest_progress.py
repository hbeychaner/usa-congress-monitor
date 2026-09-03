"""Live progress monitor for active ingest hydration jobs.

Tracks all ingest jobs in queued/running/retrying states and renders one
aggregate progress bar across remaining records, with per-job breakdowns.

Usage:
    uv run python scripts/monitor_ingest_progress.py
    uv run python scripts/monitor_ingest_progress.py --once
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from settings import CONGRESS_API_KEY, CONGRESS_API_URL, JOB_DB_PATH


@dataclass
class IngestJob:
    job_id: str
    status: str
    resource: str
    outdir: Path
    from_date: str | None
    to_date: str | None
    fetch_items: bool


def _connect_jobs() -> sqlite3.Connection:
    conn = sqlite3.connect(JOB_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _load_active_ingest_jobs(conn: sqlite3.Connection) -> list[IngestJob]:
    rows = conn.execute(
        """
        SELECT id, status, payload
        FROM jobs
        WHERE kind = 'ingest' AND status IN ('queued', 'running', 'retrying')
        ORDER BY created_at
        """
    ).fetchall()

    jobs: list[IngestJob] = []
    for row in rows:
        payload = json.loads(row["payload"])
        resources = payload.get("resources") or []
        if not resources:
            continue
        resource = str(resources[0])
        jobs.append(
            IngestJob(
                job_id=str(row["id"]),
                status=str(row["status"]),
                resource=resource,
                outdir=Path(str(payload.get("outdir", "data/full_history"))) / str(row["id"]),
                from_date=payload.get("from_date"),
                to_date=payload.get("to_date"),
                fetch_items=bool(payload.get("fetch_items", False)),
            )
        )
    return jobs


def _count_rows(db_path: Path, query: str, params: tuple[Any, ...] = ()) -> int:
    if not db_path.exists():
        return 0
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(query, params).fetchone()
    if not row:
        return 0
    return int(row[0] or 0)


def _hydrated_count(job: IngestJob) -> int:
    records_db = job.outdir / "records.sqlite3"
    return _count_rows(
        records_db,
        "SELECT count(*) FROM records WHERE resource = ?",
        (job.resource,),
    )


def _cached_list_count(job: IngestJob) -> int:
    cache_db = job.outdir / job.resource / "list_records.sqlite3"
    return _count_rows(cache_db, "SELECT count(*) FROM records")


def _checkpoint_next_offset(job: IngestJob) -> int | None:
    path = job.outdir / job.resource / "list_checkpoint.json"
    if not path.exists():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    value = state.get("next_offset")
    return int(value) if isinstance(value, int) else None


def _fetch_bill_total(job: IngestJob, cache: dict[tuple[str | None, str | None], int | None]) -> int | None:
    if job.resource != "bill" or not job.from_date or not job.to_date:
        return None

    key = (job.from_date, job.to_date)
    if key in cache:
        return cache[key]

    if not CONGRESS_API_KEY or not CONGRESS_API_URL:
        cache[key] = None
        return None

    try:
        response = requests.get(
            f"{CONGRESS_API_URL.rstrip('/')}/bill",
            params={
                "format": "json",
                "offset": 0,
                "limit": 1,
                "fromDateTime": job.from_date,
                "toDateTime": job.to_date,
            },
            headers={"x-api-key": CONGRESS_API_KEY},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        total = int(payload.get("pagination", {}).get("total", 0))
        cache[key] = total
        return total
    except Exception:
        cache[key] = None
        return None


def _bar(done: int, total: int, width: int = 44) -> str:
    if total <= 0:
        return "[" + ("-" * width) + "]"
    ratio = min(1.0, max(0.0, done / total))
    filled = int(width * ratio)
    return "[" + ("#" * filled) + ("-" * (width - filled)) + "]"


def _format_eta(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "ETA: n/a"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"ETA: {h:02d}:{m:02d}:{s:02d}"


def _render(
    jobs: list[IngestJob],
    total_hydrated: int,
    total_discovered: int,
    total_target: int,
    hydration_rate: float | None,
    discovery_rate: float | None,
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    remaining = max(0, total_target - total_hydrated)
    eta_seconds = (remaining / hydration_rate) if hydration_rate and hydration_rate > 0 else None

    lines = [
        f"Ingest Progress Monitor  {now}",
        "",
        f"Hydrated:  {total_hydrated:,}/{total_target:,} {_bar(total_hydrated, total_target)}",
        f"Discovered:{total_discovered:,}/{total_target:,} {_bar(total_discovered, total_target)}",
        (
            f"Remaining to hydrate: {remaining:,}  Hydration rate: {hydration_rate:.2f} rec/s"
            if hydration_rate is not None
            else f"Remaining to hydrate: {remaining:,}  Hydration rate: n/a"
        ),
        (
            f"List discovery rate: {discovery_rate:.2f} rec/s"
            if discovery_rate is not None
            else "List discovery rate: n/a"
        ),
        _format_eta(eta_seconds),
        "",
        "Per job:",
    ]

    for job in jobs:
        short_id = job.job_id.replace("ingest:", "")[:10]
        lines.append(
            f"- {short_id} {job.status:<8} {job.resource:<12} "
            f"hydrated {job._hydrated:,}/{job._target:,} "
            f"discovered {job._discovered:,}/{job._target:,} "
            f"(rem {max(0, job._target - job._hydrated):,})"
        )

    if not jobs:
        lines.append("- No active ingest jobs.")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Print one snapshot and exit.")
    parser.add_argument("--interval", type=float, default=10.0, help="Refresh interval in seconds.")
    args = parser.parse_args()

    total_cache: dict[tuple[str | None, str | None], int | None] = {}
    last_time: float | None = None
    last_hydrated: int | None = None
    last_discovered: int | None = None

    while True:
        with _connect_jobs() as conn:
            jobs = _load_active_ingest_jobs(conn)

        total_hydrated = 0
        total_discovered = 0
        total_target = 0

        for job in jobs:
            hydrated = _hydrated_count(job) if job.fetch_items else _cached_list_count(job)
            cached_total = _cached_list_count(job)
            api_total = _fetch_bill_total(job, total_cache)
            checkpoint_offset = _checkpoint_next_offset(job)

            if api_total and api_total > 0:
                target = max(hydrated, cached_total, api_total)
            elif checkpoint_offset == -1:
                target = max(hydrated, cached_total)
            else:
                target = max(hydrated, cached_total)

            discovered = min(target, cached_total)
            job._hydrated = hydrated  # type: ignore[attr-defined]
            job._discovered = discovered  # type: ignore[attr-defined]
            job._target = target  # type: ignore[attr-defined]
            total_hydrated += hydrated
            total_discovered += discovered
            total_target += target

        now = time.time()
        hydration_rate: float | None = None
        discovery_rate: float | None = None
        if (
            last_time is not None
            and last_hydrated is not None
            and last_discovered is not None
            and now > last_time
        ):
            elapsed = now - last_time
            hydration_rate = max(0.0, (total_hydrated - last_hydrated) / elapsed)
            discovery_rate = max(0.0, (total_discovered - last_discovered) / elapsed)
        last_time = now
        last_hydrated = total_hydrated
        last_discovered = total_discovered

        output = _render(
            jobs,
            total_hydrated,
            total_discovered,
            total_target,
            hydration_rate,
            discovery_rate,
        )
        if args.once:
            print(output)
            return

        print("\033[2J\033[H", end="")
        print(output)
        time.sleep(max(1.0, args.interval))


if __name__ == "__main__":
    main()

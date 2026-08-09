"""Plan complete historical ingest coverage as idempotent Celery jobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from cdm.ingest.resource_config import (
    congress_scoped,
    date_windowed,
    static_resources,
)
from cdm.ingest.runner import Resource


def current_utc_date() -> date:
    """Return today's UTC date for CLI defaults without local-time drift."""
    return datetime.now(UTC).date()


@dataclass(frozen=True)
class FullIngestConfig:
    """Bounds and execution settings for a complete ingest plan."""

    first_congress: int = 1
    last_congress: int = 119
    start_date: date = date(1789, 1, 1)
    end_date: date = field(default_factory=current_utc_date)
    window_days: int = 365
    outdir: str = "data/full_history"
    concurrency: int = 4
    index_batch_size: int = 500
    fetch_items: bool = True
    force_item_fetch: bool = True
    preserve_raw: bool = False

    def __post_init__(self) -> None:
        if self.first_congress < 1:
            raise ValueError("first_congress must be positive")
        if self.last_congress < self.first_congress:
            raise ValueError("last_congress must be >= first_congress")
        if self.start_date > self.end_date:
            raise ValueError("start_date must be <= end_date")
        if self.window_days < 1:
            raise ValueError("window_days must be positive")
        if self.concurrency < 1:
            raise ValueError("concurrency must be positive")
        if self.index_batch_size < 1:
            raise ValueError("index_batch_size must be positive")


@dataclass(frozen=True)
class FullIngestJob:
    """One idempotent ingest payload in a full-ingest plan."""

    label: str
    payload: dict[str, Any]


def _timestamp(value: date, *, end_of_day: bool = False) -> str:
    time = "23:59:59" if end_of_day else "00:00:00"
    return f"{value.isoformat()}T{time}Z"


def _base_payload(config: FullIngestConfig) -> dict[str, Any]:
    return {
        "outdir": config.outdir,
        "fetch_items": config.fetch_items,
        "force_item_fetch": config.force_item_fetch,
        "concurrency": config.concurrency,
        "index": True,
        "index_batch_size": config.index_batch_size,
        "preserve_raw": config.preserve_raw,
    }


def _date_windows(config: FullIngestConfig) -> list[tuple[date, date]]:
    windows: list[tuple[date, date]] = []
    current = config.start_date
    step = timedelta(days=config.window_days - 1)
    while current <= config.end_date:
        window_end = min(current + step, config.end_date)
        windows.append((current, window_end))
        current = window_end + timedelta(days=1)
    return windows


def plan_full_ingest(config: FullIngestConfig) -> list[FullIngestJob]:
    """Return idempotent jobs covering every configured resource and bound."""
    jobs: list[FullIngestJob] = []

    for resource_config in static_resources():
        resource = resource_config.resource
        payload = _base_payload(config) | {"resources": [resource.value]}
        jobs.append(FullIngestJob(f"static:{resource.value}", payload))

    for resource_config in date_windowed():
        resource = resource_config.resource
        for start, end in _date_windows(config):
            payload = _base_payload(config) | {
                "resources": [resource.value],
                "from_date": _timestamp(start),
                "to_date": _timestamp(end, end_of_day=True),
            }
            jobs.append(
                FullIngestJob(
                    f"date:{resource.value}:{start.isoformat()}:{end.isoformat()}",
                    payload,
                )
            )

    for resource_config in congress_scoped():
        resource = resource_config.resource
        for congress in range(config.first_congress, config.last_congress + 1):
            payload = _base_payload(config) | {
                "resources": [resource.value],
                "congress": congress,
            }
            jobs.append(
                FullIngestJob(f"congress:{resource.value}:{congress}", payload)
            )

    return jobs


def smoke_job(config: FullIngestConfig) -> FullIngestJob:
    """Return a bounded one-page job for validating the queue and worker."""
    payload = _base_payload(config) | {
        "resources": [Resource.CONGRESS.value],
        "max_pages": 1,
        "max_items": 1,
        "fetch_items": False,
        "force_item_fetch": False,
        "outdir": f"{config.outdir}/smoke",
    }
    return FullIngestJob("smoke:congress", payload)

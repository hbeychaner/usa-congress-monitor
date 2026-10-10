"""Builds the ingest payloads that the periodic schedulers submit."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from cdm.config.app_config import LedgerConfig
from cdm.data_collection.specs.congress_list_specs import CONGRESS_LISTABLE
from cdm.ingest.resource_config import congress_scoped, date_windowed, static_resources
from cdm.jobs.payloads import IngestMode, IngestPayload
from cdm.jobs.store import CoverageRow, JobStatus, JobStore

DATA_DAILY_DIR = "data/daily"
INGEST_CONCURRENCY = 4
INDEX_BATCH_SIZE = 500


def congress_for_year(year: int) -> int:
    return (year - 1787) // 2


def _iso_utc(moment: datetime) -> str:
    return moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


class DailyIngestPlanner:
    """Bounded recurring-ingest payload for a UTC calendar day.

    Date-capable resources are queried with a small overlap so late API
    updates are discovered. Congress-scoped resources are limited to the
    current Congress. Static resources are excluded because their endpoints
    provide no server-side incremental filter.
    """

    OVERLAP = timedelta(days=2)

    def payload(self, today: date) -> IngestPayload:
        return IngestPayload(
            outdir=DATA_DAILY_DIR,
            resources=sorted({
                config.resource.value
                for config in (*date_windowed(), *congress_scoped())
            }),
            from_date=(today - self.OVERLAP).isoformat() + "T00:00:00Z",
            to_date=today.isoformat() + "T23:59:59Z",
            congress=congress_for_year(today.year),
            fetch_items=True,
            # Bills default to list-only; daily windows are small enough to
            # hydrate full detail (actions, cosponsors, subjects, text).
            item_resources=["bill"],
            index=True,
            concurrency=INGEST_CONCURRENCY,
            index_batch_size=INDEX_BATCH_SIZE,
            schedule_date=today.isoformat(),
            mode=IngestMode.DAILY_INCREMENTAL,
        )


class CoverageGapPlanner:
    """Jobs for uncovered spans (interior holes and a stale tail)."""

    MIN_GAP = timedelta(hours=24)
    CHUNK = timedelta(days=7)
    JOBS_PER_RESOURCE = 4

    def __init__(self, store: JobStore, ledger: LedgerConfig) -> None:
        self._store = store
        self._ledger = ledger

    def holes(
        self,
        intervals: list[tuple[datetime, datetime]],
        lookback_start: datetime,
        current: datetime,
    ) -> list[tuple[datetime, datetime]]:
        """Uncovered spans after the first covered window within the lookback.

        Spans shorter than the freshness threshold are ignored; the trailing
        span up to ``current`` is included once it exceeds 24 hours.
        """
        clipped = sorted(
            (max(start, lookback_start), end)
            for start, end in intervals
            if end > lookback_start
        )
        if not clipped:
            return []
        holes: list[tuple[datetime, datetime]] = []
        covered_to = clipped[0][1]
        for start, end in clipped[1:]:
            if start - covered_to > self.MIN_GAP:
                holes.append((covered_to, start))
            covered_to = max(covered_to, end)
        if current - covered_to > self.MIN_GAP:
            holes.append((covered_to, current))
        return holes

    def chunk(self, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
        chunks: list[tuple[datetime, datetime]] = []
        while start < end:
            stop = min(end, start + self.CHUNK)
            chunks.append((start, stop))
            start = stop
        return chunks

    def payloads(self, now: datetime | None = None) -> list[IngestPayload]:
        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        lookback_start = current - timedelta(days=self._ledger.coverage_lookback_days)
        payloads: list[IngestPayload] = []
        for config in date_windowed():
            resource = config.resource.value
            intervals = self._intervals(self._store.coverage(resource))
            spans = [
                chunk
                for hole in self.holes(intervals, lookback_start, current)
                for chunk in self.chunk(*hole)
            ]
            for span_start, span_end in spans[: self.JOBS_PER_RESOURCE]:
                payloads.append(
                    IngestPayload(
                        outdir=DATA_DAILY_DIR,
                        resources=[resource],
                        from_date=_iso_utc(span_start),
                        to_date=_iso_utc(span_end),
                        # Scope to the current Congress: the bare list endpoints
                        # return records from ANY congress recently touched by
                        # Congress.gov backfills (e.g. 1978 bills with a 2026
                        # updateDate).
                        congress=congress_for_year(current.year),
                        fetch_items=config.fetch_items_default,
                        # Gap windows are small enough to hydrate full bill detail.
                        item_resources=["bill"],
                        index=True,
                        concurrency=INGEST_CONCURRENCY,
                        index_batch_size=INDEX_BATCH_SIZE,
                        mode=IngestMode.COVERAGE_GAP,
                    )
                )
        return payloads

    @staticmethod
    def _intervals(rows: list[CoverageRow]) -> list[tuple[datetime, datetime]]:
        return [
            (
                _parse_utc(row["window_start"])
                if row["window_start"]
                else datetime.min.replace(tzinfo=UTC),
                _parse_utc(row["window_end"]),
            )
            for row in rows
            if row["status"] == JobStatus.SUCCEEDED.value and row["window_end"]
        ]


class StaticRefreshPlanner:
    """Weekly refresh of static list endpoints, which ignore date filters.

    A cheap list-only pass over everything plus full hydration of the current
    Congress.
    """

    MAX_SKIPPED_LIST_PAGES = 100

    def payloads(self, today: date) -> list[IngestPayload]:
        stamp = today.isocalendar()
        week = f"{stamp.year}-W{stamp.week:02d}"
        congress = congress_for_year(today.year)
        payloads: list[IngestPayload] = []
        for config in static_resources():
            resource = config.resource.value
            base = IngestPayload(
                outdir=DATA_DAILY_DIR,
                resources=[resource],
                index=True,
                concurrency=INGEST_CONCURRENCY,
                index_batch_size=INDEX_BATCH_SIZE,
                schedule_week=week,
                # The API 500s on tail pages of some full-collection lists.
                max_skipped_list_pages=self.MAX_SKIPPED_LIST_PAGES,
            )
            payloads.append(
                base.model_copy(
                    update={"fetch_items": False, "mode": IngestMode.STATIC_REFRESH}
                )
            )
            if resource in CONGRESS_LISTABLE and config.fetch_items_default:
                payloads.append(
                    base.model_copy(
                        update={
                            "congress": congress,
                            "fetch_items": True,
                            "mode": IngestMode.STATIC_REFRESH_CONGRESS,
                        }
                    )
                )
        return payloads

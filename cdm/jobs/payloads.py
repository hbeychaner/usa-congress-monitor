"""Typed job payloads stored in the ledger and consumed by worker runners."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from cdm.utils.json_types import JsonObject


class IngestMode(StrEnum):
    DAILY_INCREMENTAL = "daily_incremental"
    COVERAGE_GAP = "coverage_gap"
    STATIC_REFRESH = "static_refresh"
    STATIC_REFRESH_CONGRESS = "static_refresh_congress"


class JobPayload(BaseModel):
    """Base payload; ``to_json`` omits unset fields so ledger job ids stay stable."""

    model_config = ConfigDict(extra="ignore")

    def to_json(self) -> JsonObject:
        return self.model_dump(mode="json", exclude_unset=True)


class IngestPayload(JobPayload):
    outdir: str
    resources: list[str] | None = None
    from_date: str | None = None
    to_date: str | None = None
    congress: int | None = None
    fetch_items: bool = False
    force_item_fetch: bool = False
    item_resources: list[str] | None = None
    max_pages: int | None = None
    max_items: int | None = None
    list_page_size: int = 250
    max_skipped_list_pages: int = 0
    concurrency: int = 1
    api_key: str | None = None
    index: bool = True
    index_batch_size: int = 500
    preserve_raw: bool = False
    mode: IngestMode | None = None
    schedule_date: str | None = None
    schedule_week: str | None = None


class IndexPayload(JobPayload):
    stream: str
    resource: str
    batch_size: int = 500
    preserve_raw: bool = False
    consumer_group: str | None = None
    expected_count: int | None = None
    archive_root: str | None = None
    target_index: str | None = None
    replace: bool = False
    source_attempt: int | None = None

    def shares_batch_with(self, other: IndexPayload) -> bool:
        return (
            self.resource == other.resource
            and self.target_index == other.target_index
            and self.replace == other.replace
            and self.preserve_raw == other.preserve_raw
        )


class GovInfoPackagePayload(JobPayload):
    collection: str
    congress: int
    measure_type: str
    package_id: str
    url: str
    session: str | None = None
    version_code: str | None = None
    outdir: str
    target_index: str | None = None
    replace: bool = False


class GovInfoBatchPayload(JobPayload):
    job_ids: list[str]


class ReconcilePayload(JobPayload):
    archive_root: str
    target_index: str
    report_path: str
    preserve_raw: bool = True

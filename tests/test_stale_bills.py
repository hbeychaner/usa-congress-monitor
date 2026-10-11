from __future__ import annotations

from pathlib import Path

from cdm.ingest.archive import LatestRecordArchive
from cdm.ingest.stale_bills import (
    IndexedBillState,
    StaleBillFilter,
)
from cdm.models.bills import BillMetadata


def _meta(number: str = "9533", update_date: str | None = "2025-01-03") -> BillMetadata:
    return BillMetadata.model_validate({
        "congress": 117,
        "number": number,
        "type": "HR",
        "title": "A bill",
        "url": "https://api.congress.gov/v3/bill/117/hr/" + number,
        "updateDate": update_date,
    })


def _filter(**states: IndexedBillState) -> StaleBillFilter:
    return StaleBillFilter({f"bill:117:hr:{key}": state for key, state in states.items()})


def test_missing_bill_is_stale() -> None:
    assert _filter().needs_refresh(_meta())


def test_newer_upstream_update_is_stale() -> None:
    state = IndexedBillState(
        update_date="2023-08-09T19:00:40Z", has_subject_data=True, hydrated=True
    )
    assert _filter(**{"9533": state}).needs_refresh(_meta())


def test_same_day_update_with_subject_data_is_fresh() -> None:
    state = IndexedBillState(
        update_date="2025-01-03T08:06:15Z", has_subject_data=True
    )
    assert not _filter(**{"9533": state}).needs_refresh(_meta())


def test_unhydrated_skeleton_without_subjects_is_stale() -> None:
    state = IndexedBillState(update_date="2025-01-03")
    assert _filter(**{"9533": state}).needs_refresh(_meta())


def test_hydrated_bill_without_subjects_is_not_refetched() -> None:
    state = IndexedBillState(update_date="2025-01-03", hydrated=True)
    assert not _filter(**{"9533": state}).needs_refresh(_meta())


def test_state_reads_subjects_and_policy_area() -> None:
    assert IndexedBillState.from_source({
        "subjects": {"legislative_subjects": [{"name": "Taxation"}]}
    }).has_subject_data
    assert IndexedBillState.from_source({
        "policy_area": {"name": "Health"}
    }).has_subject_data
    empty = IndexedBillState.from_source({"subjects": {"legislative_subjects": []}})
    assert not empty.has_subject_data
    assert not empty.hydrated


def test_latest_archive_replaces_older_record(tmp_path: Path) -> None:
    archive = LatestRecordArchive(tmp_path, 0)
    archive.write("bill", {"id": "bill:117:hr:1", "title": "old"})
    archive.write("bill", {"id": "bill:117:hr:1", "title": "new"})
    assert [record["title"] for record in archive.records("bill")] == ["new"]

"""Regression tests for archive resume dedupe across date/datetime id forms.

Bill detail payloads serialize ``introduced_date`` as a datetime
(``…:2019-01-03T00:00:00``) while list metadata serializes it as a plain
date (``…:2019-01-03``). Resume previously compared the two forms
literally, so every restart refetched all items.
"""

from cdm.ingest.archive import SQLiteListCache, SQLiteRecordArchive
from cdm.ingest.runner import IngestRunner
from cdm.models.bills import BillMetadata


def test_list_cache_round_trip_preserves_aliased_fields(tmp_path) -> None:
    meta = BillMetadata.model_validate({
        "congress": 116,
        "number": "1",
        "title": "Example",
        "type": "HCONRES",
        "url": "https://api.congress.gov/v3/bill/116/hconres/1?format=json",
        "introducedDate": "2019-01-03",
        "latestAction": {"actionDate": "2019-01-04", "text": "Received."},
    })
    cache = SQLiteListCache(tmp_path / "list_records.sqlite3")
    cache.write_many([(0, meta.model_dump(mode="json", exclude_none=True))])

    (loaded,) = cache.load(BillMetadata, -1)

    assert loaded.introduced_date == "2019-01-03"
    assert loaded.latest_action is not None
    assert IngestRunner._model_identity(loaded) == IngestRunner._model_identity(meta)


def test_normalize_record_id_strips_midnight_datetime_suffix() -> None:
    assert (
        IngestRunner._normalize_record_id("bill:116:hconres:1:2019-01-03T00:00:00")
        == "bill:116:hconres:1:2019-01-03"
    )
    assert (
        IngestRunner._normalize_record_id("bill:116:hconres:1:2019-01-03")
        == "bill:116:hconres:1:2019-01-03"
    )


def test_load_archived_item_ids_matches_date_only_list_identity(tmp_path) -> None:
    archive = SQLiteRecordArchive(tmp_path, attempt=1)
    archive.write(
        "bill",
        {
            "id": "bill:116:hconres:1",
            "introduced_date": "2019-01-03T00:00:00",
            "title": "Example",
        },
    )

    ids = IngestRunner._load_archived_item_ids(tmp_path)

    list_identity = "bill:116:hconres:1:2019-01-03"
    assert IngestRunner._normalize_record_id(list_identity) in ids


def test_bill_signature_normalizes_datetime_action_date() -> None:
    archived = {
        "congress": 116,
        "type": "HCONRES",
        "number": 1,
        "title": "Example",
        "latest_action": {
            "action_date": "2019-01-04T00:00:00",
            "text": "Received in the Senate.",
        },
    }
    list_meta = {
        "congress": 116,
        "type": "HCONRES",
        "number": 1,
        "title": "Example",
        "latest_action": {
            "action_date": "2019-01-04",
            "text": "Received in the Senate.",
        },
    }
    assert IngestRunner._bill_signature(archived) == IngestRunner._bill_signature(
        list_meta
    )

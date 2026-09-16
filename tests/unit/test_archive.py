from sqlalchemy import create_engine, func, select
from sqlalchemy.sql import table

from cdm.ingest.archive import SQLiteQuarantineArchive, SQLiteRecordArchive


def _record_count(db_path) -> int:
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as connection:
            return connection.execute(
                select(func.count()).select_from(table("records"))
            ).scalar_one()
    finally:
        engine.dispose()


def test_archive_writes_compressed_deduplicated_records(tmp_path) -> None:
    archive = SQLiteRecordArchive(tmp_path, attempt=3)

    archive.write("bill", {"id": "bill:1", "title": "First"})
    archive.write("bill", {"id": "bill:2", "title": "Second"})

    archive.write("bill", {"id": "bill:1", "title": "First"})
    assert _record_count(tmp_path / "records.sqlite3") == 2
    assert archive.ids("bill") == {"bill:1", "bill:2"}
    assert archive.records("bill") == [
        {"id": "bill:1", "title": "First"},
        {"id": "bill:2", "title": "Second"},
    ]


def test_quarantine_archive_preserves_raw_payload_and_failure_metadata(tmp_path) -> None:
    quarantine = SQLiteQuarantineArchive(tmp_path)

    quarantine.write(
        "bill",
        {"id": "bill:117:hr:1", "relationshipDetails": [{"identifiedBy": "LOC"}]},
        error="identifiedBy: unexpected value",
        source_url="https://api.congress.gov/v3/bill/117/hr/1",
    )

    records = quarantine.records("bill")
    assert len(records) == 1
    assert records[0]["record_id"] == "bill:117:hr:1"
    assert records[0]["source_url"].endswith("/bill/117/hr/1")
    assert records[0]["payload"]["relationshipDetails"][0]["identifiedBy"] == "LOC"
    assert records[0]["error"] == "identifiedBy: unexpected value"
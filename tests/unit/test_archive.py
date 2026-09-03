import sqlite3

from cdm.ingest.archive import SQLiteRecordArchive


def test_archive_writes_compressed_deduplicated_records(tmp_path) -> None:
    archive = SQLiteRecordArchive(tmp_path, attempt=3)

    archive.write("bill", {"id": "bill:1", "title": "First"})
    archive.write("bill", {"id": "bill:2", "title": "Second"})

    archive.write("bill", {"id": "bill:1", "title": "First"})
    with sqlite3.connect(tmp_path / "records.sqlite3") as connection:
        count = connection.execute("SELECT COUNT(*) FROM records").fetchone()[0]
    assert count == 2
    assert archive.ids("bill") == {"bill:1", "bill:2"}
    assert archive.records("bill") == [
        {"id": "bill:1", "title": "First"},
        {"id": "bill:2", "title": "Second"},
    ]
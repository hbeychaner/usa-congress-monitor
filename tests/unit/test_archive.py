import json

from cdm.ingest.archive import JsonlRecordArchive


def test_archive_writes_records_per_resource_and_attempt(tmp_path) -> None:
    archive = JsonlRecordArchive(tmp_path, attempt=3)

    archive.write("bill", {"id": "bill:1", "title": "First"})
    archive.write("bill", {"id": "bill:2", "title": "Second"})

    path = tmp_path / "bill" / "records-attempt-3.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines()]

    assert records == [
        {"id": "bill:1", "title": "First"},
        {"id": "bill:2", "title": "Second"},
    ]
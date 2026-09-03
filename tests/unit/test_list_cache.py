import json
import sqlite3

from cdm.ingest.archive import SQLiteListCache
from scripts.migrate_jsonl_to_sqlite import migrate


def test_list_cache_preserves_offsets_and_deduplicates(tmp_path):
    cache = SQLiteListCache(tmp_path / "list_records.sqlite3")
    cache.write(0, {"id": "bill:1", "title": "First"})
    cache.write(250, {"id": "bill:2", "title": "Second"})
    cache.write(250, {"id": "bill:2", "title": "Second"})

    class Model:
        @classmethod
        def model_validate(cls, value):
            return value

    assert cache.load(Model, 250) == [{"id": "bill:1", "title": "First"}]
    assert cache.load(Model, -1) == [
        {"id": "bill:1", "title": "First"},
        {"id": "bill:2", "title": "Second"},
    ]
    with sqlite3.connect(tmp_path / "list_records.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM records").fetchone()[0] == 2


def test_migration_verifies_and_removes_legacy_files(tmp_path):
    resource_dir = tmp_path / "bill"
    resource_dir.mkdir()
    (resource_dir / "records-attempt-1.jsonl").write_text(
        json.dumps({"id": "bill:1", "title": "First"}) + "\n"
    )
    (resource_dir / "list_records.jsonl").write_text(
        json.dumps({"offset": 0, "record": {"id": "bill:1"}}) + "\n"
    )

    assert migrate(tmp_path, delete_source=True) == (1, 1)
    assert not list(resource_dir.glob("*.jsonl"))
    assert (resource_dir / "records.sqlite3").exists()
    assert (resource_dir / "list_records.sqlite3").exists()


def test_migration_handles_legacy_items_file(tmp_path):
    resource_dir = tmp_path / "house_vote"
    resource_dir.mkdir()
    (resource_dir / "items.jsonl").write_text(
        json.dumps({"id": "vote:1", "result": "Passed"}) + "\n"
    )

    assert migrate(tmp_path, delete_source=True) == (1, 0)
    assert not (resource_dir / "items.jsonl").exists()
    with sqlite3.connect(resource_dir / "records.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM records").fetchone()[0] == 1


def test_migration_handles_json_array_without_loading_whole_file(tmp_path):
    resource_dir = tmp_path / "bill"
    resource_dir.mkdir()
    (resource_dir / "items.json").write_text(
        json.dumps([{"id": "bill:1"}, {"id": "bill:2"}])
    )

    assert migrate(tmp_path, delete_source=True) == (2, 0)
    assert not (resource_dir / "items.json").exists()
    with sqlite3.connect(resource_dir / "records.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM records").fetchone()[0] == 2
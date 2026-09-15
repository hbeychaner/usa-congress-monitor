import sqlite3

from cdm.ingest.archive import SQLiteListCache


def test_list_cache_preserves_offsets_and_deduplicates(tmp_path):
    cache = SQLiteListCache(tmp_path / "list_records.sqlite3")
    cache.write(0, {"id": "bill:1", "title": "First"})
    cache.write(250, {"id": "bill:2", "title": "Second"})
    cache.write(250, {"id": "bill:2", "title": "Second"})

    class Model:
        @classmethod
        def model_validate(cls, value, **kwargs):
            return value

    assert cache.load(Model, 250) == [{"id": "bill:1", "title": "First"}]
    assert cache.load(Model, -1) == [
        {"id": "bill:1", "title": "First"},
        {"id": "bill:2", "title": "Second"},
    ]
    with sqlite3.connect(tmp_path / "list_records.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM records").fetchone()[0] == 2

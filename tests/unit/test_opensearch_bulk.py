from cdm.store.opensearch import bulk_upsert


def test_bulk_upsert_uses_mapped_write_alias_and_idempotent_actions(monkeypatch):
    captured = {}

    def fake_bulk(client, actions, raise_on_error):
        captured["actions"] = list(actions)
        captured["raise_on_error"] = raise_on_error
        return 1, []

    monkeypatch.setattr("elasticsearch.helpers.bulk", fake_bulk)
    result = bulk_upsert(
        object(),
        "bill",
        [{"id": "bill:118:hr:1", "title": "Example"}],
    )

    assert result == {"updated": 1, "errors": False, "skipped_missing_ids": 0}
    assert captured["raise_on_error"] is False
    assert captured["actions"] == [
        {
            "_op_type": "update",
            "_index": "congress-legislation-write",
            "_id": "bill:118:hr:1",
            "doc": {"id": "bill:118:hr:1", "title": "Example"},
            "doc_as_upsert": True,
        }
    ]


def test_bulk_upsert_reports_missing_ids(monkeypatch):
    captured = {}

    def fake_bulk(client, actions, raise_on_error):
        captured["actions"] = list(actions)
        return 1, []

    monkeypatch.setattr("elasticsearch.helpers.bulk", fake_bulk)
    result = bulk_upsert(
        object(),
        "amendment",
        [{"title": "missing"}, {"id": "amendment:118:samdt:1"}],
    )

    assert result["updated"] == 1
    assert result["skipped_missing_ids"] == 1
    assert len(captured["actions"]) == 1


def test_bulk_upsert_reports_partial_failures(monkeypatch):
    def fake_bulk(client, actions, raise_on_error):
        return 1, [{"index": {"status": 400}}]

    monkeypatch.setattr("elasticsearch.helpers.bulk", fake_bulk)

    result = bulk_upsert(object(), "bill", [{"id": "bill:1"}, {"id": "bill:2"}])

    assert result == {"updated": 1, "errors": True, "skipped_missing_ids": 0}
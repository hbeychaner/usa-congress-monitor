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
    action = captured["actions"][0]
    assert action["_op_type"] == "update"
    assert action["_index"] == "congress-legislation-write"
    assert action["_id"] == "bill:118:hr:1"
    assert action["upsert"] == {"id": "bill:118:hr:1", "title": "Example"}
    assert action["scripted_upsert"] is True
    assert action["script"]["params"] == {
        "doc": {"id": "bill:118:hr:1", "title": "Example"},
    }
    assert "ctx._source" in action["script"]["source"]
    assert "instanceof List" in action["script"]["source"]


def test_bulk_upsert_keeps_non_bill_actions_on_doc_upsert(monkeypatch):
    captured = {}

    def fake_bulk(client, actions, raise_on_error):
        captured["actions"] = list(actions)
        return 1, []

    monkeypatch.setattr("elasticsearch.helpers.bulk", fake_bulk)
    bulk_upsert(object(), "member", [{"id": "member:1", "name": "Example"}])

    assert captured["actions"][0]["doc_as_upsert"] is True
    assert captured["actions"][0]["doc"] == {
        "id": "member:1",
        "name": "Example",
    }


def test_bulk_upsert_can_target_staging_index(monkeypatch):
    captured = {}

    def fake_bulk(client, actions, raise_on_error):
        captured["actions"] = list(actions)
        return 1, []

    monkeypatch.setattr("elasticsearch.helpers.bulk", fake_bulk)
    bulk_upsert(
        object(),
        "bill",
        [{"id": "bill:118:hr:1"}],
        target_index="congress-legislation-v7",
    )

    assert captured["actions"][0]["_index"] == "congress-legislation-v7"


def test_bulk_upsert_can_replace_complete_bill_document(monkeypatch):
    captured = {}

    def fake_bulk(client, actions, raise_on_error):
        captured["actions"] = list(actions)
        return 1, []

    monkeypatch.setattr("elasticsearch.helpers.bulk", fake_bulk)
    bulk_upsert(
        object(),
        "bill",
        [{"id": "bill:118:hr:1", "title": "Complete"}],
        target_index="congress-legislation-v7",
        replace=True,
    )

    action = captured["actions"][0]
    assert action["_op_type"] == "index"
    assert action["_source"] == {"id": "bill:118:hr:1", "title": "Complete"}
    assert "script" not in action


def test_bulk_upsert_replacement_is_available_for_non_bill_resources(monkeypatch):
    captured = {}

    def fake_bulk(client, actions, raise_on_error):
        captured["actions"] = list(actions)
        return 1, []

    monkeypatch.setattr("elasticsearch.helpers.bulk", fake_bulk)
    bulk_upsert(
        object(),
        "member",
        [{"id": "member:1", "name": "Complete"}],
        replace=True,
    )

    assert captured["actions"][0]["_op_type"] == "index"
    assert captured["actions"][0]["_source"] == {
        "id": "member:1",
        "name": "Complete",
    }


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

    assert result == {
        "updated": 1,
        "errors": True,
        "skipped_missing_ids": 0,
        "error_details": [{"index": {"status": 400}}],
    }

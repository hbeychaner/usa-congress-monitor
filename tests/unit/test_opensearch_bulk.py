from unittest.mock import Mock

import pytest
from elasticsearch import Elasticsearch

from cdm.store.opensearch import bulk_upsert


def test_bulk_upsert_uses_mapped_write_alias_and_idempotent_actions(monkeypatch):
    captured = {}

    def fake_bulk(client, actions, raise_on_error):
        captured["actions"] = list(actions)
        captured["raise_on_error"] = raise_on_error
        return 1, []

    monkeypatch.setattr("cdm.store.opensearch.bulk", fake_bulk)
    result = bulk_upsert(
        Mock(spec=Elasticsearch),
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


def test_bulk_upsert_merges_bill_text_onto_parent_bill(monkeypatch):
    captured = {}

    def fake_bulk(client, actions, raise_on_error):
        captured["actions"] = list(actions)
        return 1, []

    monkeypatch.setattr("cdm.store.opensearch.bulk", fake_bulk)
    bulk_upsert(
        Mock(spec=Elasticsearch),
        "bill_text",
        [
            {
                "id": "bill-text:118:hr:1:enr",
                "congress": 118,
                "type": "hr",
                "number": "1",
                "version_code": "enr",
                "full_text": "Section 1.",
            },
            # No text: produces no action.
            {
                "id": "bill-text:118:hr:2:ih",
                "congress": 118,
                "type": "hr",
                "number": "2",
            },
        ],
    )

    assert len(captured["actions"]) == 1
    action = captured["actions"][0]
    assert action["_id"] == "bill:118:hr:1"
    assert action["scripted_upsert"] is True
    params = action["script"]["params"]
    assert params["rank"] == 3
    assert params["full_text"] == "Section 1."
    assert params["base"]["id"] == "bill:118:hr:1"
    assert params["base"]["source_type"] == "bill"
    assert "full_text_version_rank" in action["script"]["source"]


def test_bulk_upsert_keeps_non_bill_actions_on_doc_upsert(monkeypatch):
    captured = {}

    def fake_bulk(client, actions, raise_on_error):
        captured["actions"] = list(actions)
        return 1, []

    monkeypatch.setattr("cdm.store.opensearch.bulk", fake_bulk)
    bulk_upsert(
        Mock(spec=Elasticsearch), "member", [{"id": "member:1", "name": "Example"}]
    )

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

    monkeypatch.setattr("cdm.store.opensearch.bulk", fake_bulk)
    bulk_upsert(
        Mock(spec=Elasticsearch, indices=Mock()),
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

    monkeypatch.setattr("cdm.store.opensearch.bulk", fake_bulk)
    bulk_upsert(
        Mock(spec=Elasticsearch, indices=Mock()),
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

    monkeypatch.setattr("cdm.store.opensearch.bulk", fake_bulk)
    bulk_upsert(
        Mock(spec=Elasticsearch),
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

    monkeypatch.setattr("cdm.store.opensearch.bulk", fake_bulk)
    result = bulk_upsert(
        Mock(spec=Elasticsearch),
        "amendment",
        [{"title": "missing"}, {"id": "amendment:118:samdt:1"}],
    )

    assert result["updated"] == 1
    assert result["skipped_missing_ids"] == 1
    assert len(captured["actions"]) == 1


def test_bulk_upsert_reports_partial_failures(monkeypatch):
    def fake_bulk(client, actions, raise_on_error):
        return 1, [{"index": {"status": 400}}]

    monkeypatch.setattr("cdm.store.opensearch.bulk", fake_bulk)

    with pytest.raises(RuntimeError, match="Bulk indexing failed.*400"):
        bulk_upsert(
            Mock(spec=Elasticsearch), "bill", [{"id": "bill:1"}, {"id": "bill:2"}]
        )


def test_bulk_failure_keeps_every_rejected_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    errors = [
        {"update": {"_index": "staging", "_id": f"bill:{number}", "status": 400}}
        for number in range(5)
    ]
    monkeypatch.setattr("cdm.store.opensearch.bulk", Mock(return_value=(0, errors)))
    with pytest.raises(RuntimeError) as failure:
        bulk_upsert(Mock(spec=Elasticsearch), "bill", [{"id": "bill:1"}])
    assert str(failure.value) == f"Bulk indexing failed: {errors}"


class TestCanonicalTextProjection:
    @pytest.mark.parametrize("target", [None, "congress-legislation-staging"])
    def test_replace_preserves_the_live_parent_projection(
        self, monkeypatch: pytest.MonkeyPatch, target: str | None
    ) -> None:
        bulk = Mock(return_value=(1, []))
        monkeypatch.setattr("cdm.store.opensearch.bulk", bulk)
        client = Mock(spec=Elasticsearch, indices=Mock())
        client.indices.exists.return_value = True
        text = {
            "id": "bill-text:118:hr:1:enr",
            "congress": 118,
            "type": "hr",
            "number": "1",
            "version_code": "enr",
            "full_text": "Section 1.",
            "full_text_lemma": "section 1",
        }

        bulk_upsert(client, "bill_text", [text], target_index=target)
        live_actions = bulk.call_args.args[1]
        bulk_upsert(client, "bill_text", [text], target_index=target, replace=True)
        replay_actions = bulk.call_args.args[1]

        assert replay_actions == live_actions
        assert replay_actions[0]["_op_type"] == "update"
        assert replay_actions[0]["_id"] == "bill:118:hr:1"
        assert replay_actions[0]["script"]["params"]["full_text_lemma"] == "section 1"
        assert replay_actions[0]["script"]["params"]["rank"] == 3

    @pytest.mark.parametrize("target", ["congress-legislation-missing", "", "  "])
    @pytest.mark.parametrize("replace", [False, True])
    def test_explicit_missing_destination_never_reaches_bulk(
        self, monkeypatch: pytest.MonkeyPatch, target: str, replace: bool
    ) -> None:
        bulk = Mock()
        monkeypatch.setattr("cdm.store.opensearch.bulk", bulk)
        client = Mock(spec=Elasticsearch, indices=Mock())
        client.indices.exists.return_value = False

        with pytest.raises(ValueError, match="Explicit index target"):
            bulk_upsert(
                client,
                "bill",
                [{"id": "bill:118:hr:1"}],
                target_index=target,
                replace=replace,
            )

        bulk.assert_not_called()
        client.indices.create.assert_not_called()

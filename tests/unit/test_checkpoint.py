import json

from cdm.ingest import checkpoint


def test_checkpoint_save_load_and_clear(tmp_path):
    state = {"offset": 250, "last_processed_id": "bill:118:hr:1"}

    checkpoint.save("bill", state, tmp_path)

    path = tmp_path / "bill.json"
    assert json.loads(path.read_text()) == state
    assert checkpoint.load("bill", tmp_path) == state

    checkpoint.clear("bill", tmp_path)

    assert not path.exists()
    assert checkpoint.load("bill", tmp_path) == {}


def test_checkpoint_save_replaces_existing_state(tmp_path):
    checkpoint.save("amendment", {"offset": 250}, tmp_path)
    checkpoint.save("amendment", {"offset": 500}, tmp_path)

    assert checkpoint.load("amendment", tmp_path) == {"offset": 500}
    assert not list(tmp_path.glob("*.tmp"))

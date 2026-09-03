from cdm.ingest.runner import Resource
from scripts.ingest_history import _is_done


def test_is_done_requires_nonempty_resource_metadata(tmp_path):
    assert _is_done(tmp_path, Resource.BILL, fetch_items=False) is False

    metadata_path = tmp_path / Resource.BILL.value / "meta.json"
    metadata_path.parent.mkdir()
    metadata_path.write_text(
        '{"resource": "bill", "fetch_items": false}', encoding="utf-8"
    )

    assert _is_done(tmp_path, Resource.BILL, fetch_items=False) is True
    assert _is_done(tmp_path, Resource.BILL, fetch_items=True) is False

    metadata_path.write_text(
        '{"resource": "bill", "fetch_items": true}', encoding="utf-8"
    )
    assert _is_done(tmp_path, Resource.BILL, fetch_items=True) is True
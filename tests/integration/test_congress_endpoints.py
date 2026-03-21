"""Integration test to exercise the congress list + item endpoints.

Run with: `export PYTHONPATH=$PWD && pytest -q tests/integration/test_congress_endpoints.py`
"""

from pprint import pprint

from src.data_collection.client import get_client, resolve_runtime_params_from_record
from src.data_collection.specs.congress_specs import CONGRESS_LIST_SPEC, CONGRESS_ITEM_SPEC


def test_congress_list_and_items():
    client = get_client()

    # list
    list_items = client.fetch_list(CONGRESS_LIST_SPEC)
    assert len(list_items) > 0

    # sample output for humans when running directly
    print(f"Retrieved {len(list_items)} congress metadata records")
    pprint(list_items[0].model_dump())

    # each metadata should resolve runtime params and fetch the item
    errors = []
    for meta in list_items:
        display_name = getattr(meta, "name", None) or meta.model_dump().get("name")
        runtime_params = resolve_runtime_params_from_record(
            client, CONGRESS_ITEM_SPEC, meta
        )
        if not runtime_params:
            errors.append((display_name, "could not resolve runtime params"))
            continue
        inst = client.fetch_one(CONGRESS_ITEM_SPEC, runtime_params)
        assert inst is not None

    assert not errors, f"Errors fetching items: {errors[:10]}"

import pytest
import traceback

from src.data_collection.queueing import specs
from src.data_collection.client import client as cdg_client


@pytest.mark.integration
def test_response_coercion_all_endpoints():
    """Ensure each spec's response_model can coerce a single-page response."""
    fails = []
    for key, spec in specs.SPECS.items():
        if spec.response_model is None:
            continue
        try:
            # Use the fetch helpers to get one page (safe defaults are handled by specs)
            # Determine sensible offset/limit for single fetch
            if spec.endpoint == "congress":
                raw = specs.fetch_page(spec.endpoint, cdg_client, offset=117, limit=1, meta=None)
            elif spec.endpoint == "law":
                raw = specs.fetch_law_page(cdg_client, congress=117, offset=0, limit=1)
            else:
                raw = specs.fetch_page(spec.endpoint, cdg_client, offset=0, limit=1, meta=None)
        except Exception as e:
            fails.append((key, f"fetch_error: {e}"))
            continue
        try:
            spec.response_model.model_validate(raw)
        except Exception as e:
            tb = traceback.format_exc()
            fails.append((key, f"coercion_error: {e}\n{tb}"))

    assert not fails, f"Some endpoints failed coercion: {fails}"

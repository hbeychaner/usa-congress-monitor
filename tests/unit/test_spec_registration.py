import pytest

import src.data_collection.specs  # registers specs
from src.data_collection.endpoint_registry import all_specs
from src.data_collection.client import get_client


def test_registered_specs_resolve_models():
    client = get_client()
    specs = all_specs()
    assert specs, "no specs registered"
    for name, spec in specs.items():
        # some specs intentionally omit response_model; skip those
        if getattr(spec, "response_model", None) is None:
            continue
        model_cls = client._resolve_response_model(spec)
        assert model_cls is not None
        # ensure it's a Pydantic model class
        from pydantic import BaseModel as PydBase

        assert issubclass(model_cls, PydBase)

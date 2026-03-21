from types import SimpleNamespace

from src.data_collection.client import resolve_runtime_params_from_record
from src.models.endpoint_spec import ParamLocation, ParamSpec


def test_runtime_params_lowercases_path_strings():
    # Build a minimal spec with path params that map from source fields
    spec = SimpleNamespace(
        param_specs=[
            ParamSpec(
                name="congress",
                location=ParamLocation.PATH,
                required=True,
                source_field="congress",
            ),
            ParamSpec(
                name="type",
                location=ParamLocation.PATH,
                required=True,
                source_field="type",
            ),
            ParamSpec(
                name="number",
                location=ParamLocation.PATH,
                required=True,
                source_field="number",
                extract_from_url_segment="amendment",
            ),
        ]
    )

    record = {"congress": 109, "type": "HAMDT", "number": "2"}

    params = resolve_runtime_params_from_record(object(), spec, record)

    assert params["congress"] == 109
    # type should be lowercased for path param
    assert params["type"] == "hamdt"
    assert params["number"] == "2"

from src.data_collection.queueing.specs import SPECS


def test_all_response_models_accept_empty_lists():
    failures = []
    for name, spec in SPECS.items():
        if spec.response_model is not None:
            try:
                raw = {spec.api_data_key: [], "pagination": {}}
                spec.response_model.model_validate(raw)
            except Exception as exc:
                failures.append((name, str(exc)))
    assert not failures, f"Response model parsing failed for: {failures}"

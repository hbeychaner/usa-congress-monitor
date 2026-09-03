import os

import pytest

from cdm.data_collection.client import get_client
from cdm.data_collection.endpoint_registry import get_spec
from cdm.ingest.resource_config import get_config
from cdm.ingest.runner import Resource
from settings import CONGRESS_API_KEY

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def live_client():
    if not (os.getenv("CONGRESS_API_KEY") or CONGRESS_API_KEY):
        pytest.skip("Congress.gov API key is not configured")
    return get_client()


def _assert_raw_keys_preserved(raw_record, model):
    dumped = model.model_dump(mode="json", by_alias=True, exclude_none=True)
    missing = {
        key
        for key, value in raw_record.items()
        if value is not None and key not in dumped
    }
    assert not missing, f"validated model dropped API fields: {sorted(missing)}"


def _fetch_first_record(client, resource):
    list_spec = get_spec(resource.list_spec_name())
    params = {}
    config = get_config(resource)
    if config.requires_congress:
        params["congress"] = 118
    if resource is Resource.SUMMARIES:
        params = {
            "fromDateTime": "2025-01-01T00:00:00Z",
            "toDateTime": "2025-01-31T23:59:59Z",
        }
    response = client.request_for_spec(list_spec, params)
    records = client._extract_records_from_response(list_spec, response)
    models = client.coerce_records(
        client._resolve_response_model(list_spec), records[:1], spec=list_spec
    )
    assert models, f"{resource.value} list returned no records"
    _assert_raw_keys_preserved(records[0], models[0])
    return list_spec, records[0], models[0]


def test_live_committee_meeting_preserves_and_validates_fields(live_client):
    _, raw_record, list_model = _fetch_first_record(
        live_client, Resource.COMMITTEE_MEETING
    )
    assert list_model.event_id is not None

    item_spec = get_spec(Resource.COMMITTEE_MEETING.item_spec_name())
    params = live_client.resolve_runtime_params_from_record(item_spec, list_model)
    response = live_client.request_for_spec(item_spec, params)
    item_records = live_client._extract_records_from_response(item_spec, response)
    item_models = live_client.coerce_records(
        live_client._resolve_response_model(item_spec), item_records, spec=item_spec
    )
    assert item_models
    _assert_raw_keys_preserved(item_records[0], item_models[0])
    assert int(raw_record["eventId"]) == list_model.event_id


def test_live_committee_print_preserves_and_validates_fields(live_client):
    _, raw_record, list_model = _fetch_first_record(
        live_client, Resource.COMMITTEE_PRINT
    )
    assert list_model.jacket_number is not None

    item_spec = get_spec(Resource.COMMITTEE_PRINT.item_spec_name())
    params = live_client.resolve_runtime_params_from_record(item_spec, list_model)
    response = live_client.request_for_spec(item_spec, params)
    item_records = live_client._extract_records_from_response(item_spec, response)
    item_models = live_client.coerce_records(
        live_client._resolve_response_model(item_spec), item_records, spec=item_spec
    )
    assert item_models
    _assert_raw_keys_preserved(item_records[0], item_models[0])
    assert raw_record["jacketNumber"] == list_model.jacket_number


def test_live_summaries_preserves_and_validates_fields(live_client):
    _, raw_record, list_model = _fetch_first_record(live_client, Resource.SUMMARIES)
    assert list_model.bill is not None
    _assert_raw_keys_preserved(raw_record, list_model)


@pytest.mark.parametrize("resource", list(Resource), ids=lambda resource: resource.value)
def test_live_resource_list_preserves_and_validates_fields(live_client, resource):
    """Validate one real list record for every configured resource."""
    _, raw_record, list_model = _fetch_first_record(live_client, resource)
    _assert_raw_keys_preserved(raw_record, list_model)

from cdm.data_collection.endpoint_registry import get_spec
from cdm.ingest.resource_config import (
    RESOURCE_CONFIGS,
    congress_scoped,
    effective_scope,
    list_spec_requires_congress,
    static_resources,
)
from cdm.ingest.runner import Resource


def test_congress_scope_follows_list_spec_path_parameters():
    assert list_spec_requires_congress(Resource.LAW)
    assert not list_spec_requires_congress(Resource.HOUSE_VOTE)

    congress_resources = {config.resource for config in congress_scoped()}
    static_resources_set = {config.resource for config in static_resources()}

    assert congress_resources == {Resource.LAW}
    assert Resource.HOUSE_VOTE in static_resources_set
    assert effective_scope(RESOURCE_CONFIGS[Resource.HOUSE_VOTE]) == "static"


def test_house_vote_list_spec_is_global():
    house_vote_list = get_spec("house_vote_list")

    assert house_vote_list.path_template == "/house-vote"
    assert house_vote_list.param_specs == []


def test_congress_scoped_resources_have_registered_list_specs():
    for config in congress_scoped():
        assert get_spec(f"{config.resource.value}_list").response_model is not None
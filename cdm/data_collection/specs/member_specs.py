from cdm.data_collection.endpoint_registry import (
    EndpointSpec,
    ParamLocation,
    ParamSpec,
    get_spec,
    register_specs,
)
from cdm.models.people import Member
from cdm.models.people_lists import MemberListItem

# list endpoint
list_spec = EndpointSpec(
    name="member_list",
    path_template="/member",
    param_specs=[],
    data_key="members",
    response_model=MemberListItem,
)

# item endpoint (bioguide id in path)
item_spec = EndpointSpec(
    name="member_item",
    path_template="/member/{bioguideId}",
    param_specs=[
        ParamSpec(
            name="bioguideId",
            location=ParamLocation.PATH,
            required=True,
            source_field="bioguideId",
            extract_from_url_segment="member",
        )
    ],
    data_key=None,
    unwrap_key="member",
    response_model=Member,
)

register_specs(list_spec, item_spec)

MEMBER_LIST_SPEC = get_spec("member_list")
MEMBER_ITEM_SPEC = get_spec("member_item")

__all__ = ["MEMBER_ITEM_SPEC", "MEMBER_LIST_SPEC"]

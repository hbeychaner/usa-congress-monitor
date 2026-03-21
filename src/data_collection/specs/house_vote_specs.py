from src.data_collection.endpoint_registry import (
    EndpointSpec,
    ParamLocation,
    ParamSpec,
    get_spec,
    register_specs,
)

# House roll call votes (beta)
from src.models.legislation import HouseRollCallVoteListItem


list_spec = EndpointSpec(
    name="house_vote_list",
    path_template="/house-vote",
    param_specs=[],
    data_key="houseRollCallVotes",
    response_model=HouseRollCallVoteListItem,
)

item_spec = EndpointSpec(
    name="house_vote_item",
    path_template="/house-vote/{path_tail}",
    param_specs=[
        ParamSpec(
            name="path_tail",
            location=ParamLocation.PATH,
            required=True,
            source_field="_unused",
            extract_from_url_segment="house-vote",
        )
    ],
    data_key=None,
    unwrap_key="houseRollCallVote",
    response_model=HouseRollCallVoteListItem,
)

register_specs(list_spec, item_spec)

HOUSE_VOTE_LIST = get_spec("house_vote_list")
HOUSE_VOTE_ITEM = get_spec("house_vote_item")

__all__ = ["HOUSE_VOTE_LIST", "HOUSE_VOTE_ITEM"]

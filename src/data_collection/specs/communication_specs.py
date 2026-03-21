from src.data_collection.endpoint_registry import (
    EndpointSpec,
    ParamLocation,
    ParamSpec,
    get_spec,
    register_spec,
    register_specs,
)
from src.models.other_models import (
    HouseCommunicationListItem,
    HouseCommunication,
    SenateCommunicationListItem,
    SenateCommunication,
)


# House communications
house_list = EndpointSpec(
    name="house_communication_list",
    path_template="/house-communication",
    param_specs=[],
    data_key="houseCommunications",
    response_model=HouseCommunicationListItem,
)

house_item = EndpointSpec(
    name="house_communication_item",
    path_template="/house-communication/{path_tail}",
    param_specs=[
        ParamSpec(
            name="path_tail",
            location=ParamLocation.PATH,
            required=True,
            source_field="_unused",
            extract_from_url_segment="house-communication",
        )
    ],
    data_key=None,
    unwrap_key="houseCommunication",
    response_model=HouseCommunication,
)

register_specs(house_list, house_item)

# Senate communications
senate_list = EndpointSpec(
    name="senate_communication_list",
    path_template="/senate-communication",
    param_specs=[],
    data_key="senateCommunications",
    response_model=SenateCommunicationListItem,
)

senate_item = EndpointSpec(
    name="senate_communication_item",
    path_template="/senate-communication/{path_tail}",
    param_specs=[
        ParamSpec(
            name="path_tail",
            location=ParamLocation.PATH,
            required=True,
            source_field="_unused",
            extract_from_url_segment="senate-communication",
        )
    ],
    data_key=None,
    unwrap_key="senateCommunication",
    response_model=SenateCommunication,
)

register_specs(senate_list, senate_item)

HOUSE_COMMUNICATION_LIST = get_spec("house_communication_list")
HOUSE_COMMUNICATION_ITEM = get_spec("house_communication_item")
SENATE_COMMUNICATION_LIST = get_spec("senate_communication_list")
SENATE_COMMUNICATION_ITEM = get_spec("senate_communication_item")

__all__ = [
    "HOUSE_COMMUNICATION_LIST",
    "HOUSE_COMMUNICATION_ITEM",
    "SENATE_COMMUNICATION_LIST",
    "SENATE_COMMUNICATION_ITEM",
]

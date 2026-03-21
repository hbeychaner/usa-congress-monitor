from src.data_collection.endpoint_registry import (
    EndpointSpec,
    ParamLocation,
    ParamSpec,
    get_spec,
    register_specs,
)
from src.models.other_models import HouseRequirementListItem, HouseRequirement


list_spec = EndpointSpec(
    name="house_requirement_list",
    path_template="/house-requirement",
    param_specs=[],
    data_key="houseRequirements",
    response_model=HouseRequirementListItem,
)

item_spec = EndpointSpec(
    name="house_requirement_item",
    path_template="/house-requirement/{path_tail}",
    param_specs=[
        ParamSpec(
            name="path_tail",
            location=ParamLocation.PATH,
            required=True,
            source_field="_unused",
            extract_from_url_segment="house-requirement",
        )
    ],
    data_key=None,
    response_model=HouseRequirement,
)

register_specs(list_spec, item_spec)

HOUSE_REQUIREMENT_LIST = get_spec("house_requirement_list")
HOUSE_REQUIREMENT_ITEM = get_spec("house_requirement_item")

__all__ = ["HOUSE_REQUIREMENT_LIST", "HOUSE_REQUIREMENT_ITEM"]

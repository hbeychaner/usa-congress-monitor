from src.data_collection.endpoint_registry import (
    EndpointSpec,
    ParamLocation,
    ParamSpec,
    get_spec,
    register_specs,
)
from src.models.other_models import HearingListItem
from src.models.bills import Hearing


list_spec = EndpointSpec(
    name="hearing_list",
    path_template="/hearing",
    param_specs=[],
    data_key="hearings",
    response_model=HearingListItem,
)

item_spec = EndpointSpec(
    name="hearing_item",
    path_template="/hearing/{path_tail}",
    param_specs=[
        ParamSpec(
            name="path_tail",
            location=ParamLocation.PATH,
            required=True,
            source_field="_unused",
            extract_from_url_segment="hearing",
        )
    ],
    data_key=None,
    unwrap_key="hearing",
    response_model=Hearing,
)

register_specs(list_spec, item_spec)

HEARING_LIST_SPEC = get_spec("hearing_list")
HEARING_ITEM_SPEC = get_spec("hearing_item")

__all__ = ["HEARING_LIST_SPEC", "HEARING_ITEM_SPEC"]

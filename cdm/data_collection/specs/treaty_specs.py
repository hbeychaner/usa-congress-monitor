from cdm.data_collection.endpoint_registry import (
    EndpointSpec,
    ParamLocation,
    ParamSpec,
    get_spec,
    register_specs,
)
from cdm.models.bills import Treaty
from cdm.models.other_models import TreatyListItem

list_spec = EndpointSpec(
    name="treaty_list",
    path_template="/treaty",
    param_specs=[],
    data_key="treaties",
    response_model=TreatyListItem,
)

item_spec = EndpointSpec(
    name="treaty_item",
    path_template="/treaty/{path_tail}",
    param_specs=[
        ParamSpec(
            name="path_tail",
            location=ParamLocation.PATH,
            required=True,
            source_field="_unused",
            extract_from_url_segment="treaty",
        )
    ],
    data_key=None,
    unwrap_key="treaty",
    response_model=Treaty,
)

register_specs(list_spec, item_spec)

TREATY_LIST = get_spec("treaty_list")
TREATY_ITEM = get_spec("treaty_item")

__all__ = ["TREATY_ITEM", "TREATY_LIST"]

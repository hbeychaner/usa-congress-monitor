from src.data_collection.endpoint_registry import (
    EndpointSpec,
    ParamLocation,
    ParamSpec,
    get_spec,
    register_specs,
)
from src.models.other_models import Nomination, NominationListItem

list_spec = EndpointSpec(
    name="nomination_list",
    path_template="/nomination",
    param_specs=[],
    data_key="nominations",
    response_model=NominationListItem,
)

item_spec = EndpointSpec(
    name="nomination_item",
    path_template="/nomination/{congress}/{nomination_number}",
    param_specs=[
        ParamSpec(
            name="congress",
            location=ParamLocation.PATH,
            required=True,
            source_field="congress",
        ),
        ParamSpec(
            name="nomination_number",
            location=ParamLocation.PATH,
            required=True,
            source_field="number",
            extract_from_url_segment="nomination",
        ),
    ],
    data_key=None,
    unwrap_key="nomination",
    response_model=Nomination,
)

register_specs(list_spec, item_spec)

NOMINATION_LIST_SPEC = get_spec("nomination_list")
NOMINATION_ITEM_SPEC = get_spec("nomination_item")

__all__ = ["NOMINATION_LIST_SPEC", "NOMINATION_ITEM_SPEC"]

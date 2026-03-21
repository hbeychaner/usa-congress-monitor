from src.data_collection.endpoint_registry import (
    EndpointSpec,
    ParamLocation,
    ParamSpec,
    get_spec,
    register_specs,
)
from src.models.bills import Amendment
from src.models.other_models import AmendmentListItem

# The Congress.gov amendment endpoints use the path form:
#  - list: /amendment
#  - item: /amendment/{congress}/{type}/{number}
# Build explicit specs so runtime param resolution produces the three path params
list_spec = EndpointSpec(
    name="amendment_list",
    path_template="/amendment",
    param_specs=[],
    data_key="amendments",
    response_model=AmendmentListItem,
)

item_spec = EndpointSpec(
    name="amendment_item",
    path_template="/amendment/{congress}/{type}/{number}",
    param_specs=[
        ParamSpec(
            name="congress",
            location=ParamLocation.PATH,
            required=True,
            source_field="congress",
        ),
        ParamSpec(
            name="type", location=ParamLocation.PATH, required=True, source_field="type"
        ),
        ParamSpec(
            name="number",
            location=ParamLocation.PATH,
            required=True,
            source_field="number",
            extract_from_url_segment="amendment",
        ),
    ],
    data_key=None,
    unwrap_key="amendment",
    response_model=Amendment,
)

register_specs(list_spec, item_spec)


AMENDMENT_LIST_SPEC = get_spec("amendment_list")
AMENDMENT_ITEM_SPEC = get_spec("amendment_item")

__all__ = ["AMENDMENT_LIST_SPEC", "AMENDMENT_ITEM_SPEC"]

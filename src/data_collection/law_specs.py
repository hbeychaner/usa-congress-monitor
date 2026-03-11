from src.models.other_models import LawListItem
from src.models.bills import Law
from src.data_collection.endpoint_registry import (
    EndpointSpec,
    ParamSpec,
    ParamLocation,
    register_specs,
    get_spec,
)


# The Congress.gov law endpoints are documented separately but reuse the
# bill element structure. Implement specs matching the OpenAPI paths:
#  - list: /law/{congress} (returns `bills` list)
#  - item: /law/{congress}/{lawType}/{lawNumber} (returns a `bill` item)
list_spec = EndpointSpec(
    name="law_list",
    path_template="/law/{congress}",
    param_specs=[
        ParamSpec(name="congress", location=ParamLocation.PATH, required=True, source_field="congress")
    ],
    data_key="bills",
    response_model=LawListItem,
)

# Item endpoint: extract law type/number from the nested `laws` array in
# list records using dotted `source_field` notation (handled by the resolver).
item_spec = EndpointSpec(
    name="law_item",
    path_template="/law/{congress}/{lawType}/{lawNumber}",
    param_specs=[
        ParamSpec(name="congress", location=ParamLocation.PATH, required=True, source_field="congress"),
        ParamSpec(name="lawType", location=ParamLocation.PATH, required=True, source_field="laws.0.type"),
        ParamSpec(name="lawNumber", location=ParamLocation.PATH, required=True, source_field="laws.0.number"),
    ],
    data_key=None,
    unwrap_key="bill",
    response_model=Law,
)

register_specs(list_spec, item_spec)


LAW_LIST_SPEC = get_spec("law_list")
LAW_ITEM_SPEC = get_spec("law_item")

__all__ = ["LAW_LIST_SPEC", "LAW_ITEM_SPEC"]

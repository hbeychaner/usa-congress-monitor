from src.data_collection.endpoint_registry import (
    EndpointSpec,
    ParamLocation,
    ParamSpec,
    get_spec,
    register_specs,
)
from src.models.endpoint_spec import EndpointSpec as ModelEndpointSpec
from src.models.other_models import BoundCongressionalRecordListItem

# list endpoint
list_spec = EndpointSpec(
    name="bound_congressional_record_list",
    path_template="/bound-congressional-record",
    param_specs=[],
    data_key="boundCongressionalRecord",
    id_strategy=ModelEndpointSpec.IdStrategy(
        reference_from="url", unique_from=["date"], section_bounds="sections.0"
    ),
    response_model=BoundCongressionalRecordListItem,
)

# item endpoint: accept a single tail parameter extracted from the list `url`
# e.g. /bound-congressional-record/1947/3/17
item_spec = EndpointSpec(
    name="bound_congressional_record_item",
    path_template="/bound-congressional-record/{path_tail}",
    param_specs=[
        ParamSpec(
            name="path_tail",
            location=ParamLocation.PATH,
            required=True,
            source_field="_unused",
            extract_from_url_segment="bound-congressional-record",
        )
    ],
    data_key=None,
    response_model=BoundCongressionalRecordListItem,
    id_strategy=ModelEndpointSpec.IdStrategy(
        reference_from="url", unique_from=["date"], section_bounds="sections.0"
    ),
)

register_specs(list_spec, item_spec)

BOUND_CONGRESSIONAL_RECORD_LIST_SPEC = get_spec("bound_congressional_record_list")
BOUND_CONGRESSIONAL_RECORD_ITEM_SPEC = get_spec("bound_congressional_record_item")

__all__ = [
    "BOUND_CONGRESSIONAL_RECORD_LIST_SPEC",
    "BOUND_CONGRESSIONAL_RECORD_ITEM_SPEC",
]

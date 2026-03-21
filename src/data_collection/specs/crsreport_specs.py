from src.data_collection.endpoint_registry import (
    EndpointSpec,
    ParamLocation,
    ParamSpec,
    get_spec,
    register_specs,
)
from src.models.other_models import CRSReport


# list endpoint
list_spec = EndpointSpec(
    name="crsreport_list",
    path_template="/crsreport",
    param_specs=[],
    data_key="CRSReports",
    response_model=CRSReport,
)

# item endpoint: accept id extracted from URL
item_spec = EndpointSpec(
    name="crsreport_item",
    path_template="/crsreport/{id}",
    param_specs=[
        ParamSpec(
            name="id",
            location=ParamLocation.PATH,
            required=True,
            source_field="id",
            extract_from_url_segment="crsreport",
        )
    ],
    data_key=None,
    unwrap_key="CRSReport",
    response_model=CRSReport,
)

register_specs(list_spec, item_spec)

CRSREPORT_LIST_SPEC = get_spec("crsreport_list")
CRSREPORT_ITEM_SPEC = get_spec("crsreport_item")

__all__ = ["CRSREPORT_LIST_SPEC", "CRSREPORT_ITEM_SPEC"]

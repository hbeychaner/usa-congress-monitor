from src.models.bills import (
    Bill,
    BillMetadata,
    BillTextResponse,
    BillActionsResponse,
    BillAmendmentsResponse,
    BillCommitteesResponse,
    BillCosponsorsResponse,
    BillRelatedBillsResponse,
    BillSubjectsResponse,
    BillSummariesResponse,
    BillTitlesResponse,
)
from src.data_collection.endpoint_registry import (
    EndpointSpec,
    ParamSpec,
    ParamLocation,
    register_spec,
    register_specs,
    get_spec,
)

# The Congress.gov bill endpoints use the path form:
#  - list: /bill/{congress}
#  - item: /bill/{congress}/{type}/{number}
# Build explicit specs so runtime param resolution produces the three path params
list_spec = EndpointSpec(
    name="bill_list",
    path_template="/bill",
    param_specs=[],
    data_key="bills",
    response_model=BillMetadata,
)

item_spec = EndpointSpec(
    name="bill_item",
    path_template="/bill/{congress}/{type}/{number}",
    param_specs=[
            ParamSpec(name="congress", location=ParamLocation.PATH, required=True, source_field="congress"),
            ParamSpec(name="type", location=ParamLocation.PATH, required=True, source_field="type"),
        ParamSpec(
            name="number",
            location=ParamLocation.PATH,
            required=True,
            source_field="number",
            extract_from_url_segment="bill",
        ),
    ],
    data_key=None,
    unwrap_key="bill",
    response_model=Bill,
)

register_specs(list_spec, item_spec)


BILL_LIST_SPEC = get_spec("bill_list")
BILL_ITEM_SPEC = get_spec("bill_item")

__all__ = ["BILL_LIST_SPEC", "BILL_ITEM_SPEC"]

def _path_params_for_bill():
    return [
        ParamSpec(name="congress", location=ParamLocation.PATH, required=True, source_field="congress"),
        ParamSpec(name="billType", location=ParamLocation.PATH, required=True, source_field="type"),
        ParamSpec(name="billNumber", location=ParamLocation.PATH, required=True, source_field="number"),
    ]


bill_list_all = EndpointSpec(
    name="bill_list_all",
    path_template="/bill",
    param_specs=[],
    data_key="bills",
)

bill_list_by_congress = EndpointSpec(
    name="bill_list_by_congress",
    path_template="/bill/{congress}",
    param_specs=[ParamSpec(name="congress", location=ParamLocation.PATH, required=True, source_field="congress")],
    data_key="bills",
)

bill_list_by_type = EndpointSpec(
    name="bill_list_by_type",
    path_template="/bill/{congress}/{billType}",
    param_specs=[
        ParamSpec(name="congress", location=ParamLocation.PATH, required=True, source_field="congress"),
        ParamSpec(name="billType", location=ParamLocation.PATH, required=True, source_field="type"),
    ],
    data_key="bills",
)

bill_details = EndpointSpec(
    name="bill_details",
    path_template="/bill/{congress}/{billType}/{billNumber}",
    param_specs=_path_params_for_bill(),
    data_key=None,
    unwrap_key="bill",
    response_model=Bill,
)

bill_actions = EndpointSpec(
    name="bill_actions",
    path_template="/bill/{congress}/{billType}/{billNumber}/actions",
    param_specs=_path_params_for_bill(),
    data_key=None,
    response_model=BillActionsResponse,
)

bill_amendments = EndpointSpec(
    name="bill_amendments",
    path_template="/bill/{congress}/{billType}/{billNumber}/amendments",
    param_specs=_path_params_for_bill(),
    data_key=None,
    response_model=BillAmendmentsResponse,
)

bill_committees = EndpointSpec(
    name="bill_committees",
    path_template="/bill/{congress}/{billType}/{billNumber}/committees",
    param_specs=_path_params_for_bill(),
    data_key=None,
    response_model=BillCommitteesResponse,
)

bill_cosponsors = EndpointSpec(
    name="bill_cosponsors",
    path_template="/bill/{congress}/{billType}/{billNumber}/cosponsors",
    param_specs=_path_params_for_bill(),
    data_key=None,
    response_model=BillCosponsorsResponse,
)

bill_relatedbills = EndpointSpec(
    name="bill_relatedbills",
    path_template="/bill/{congress}/{billType}/{billNumber}/relatedbills",
    param_specs=_path_params_for_bill(),
    data_key=None,
    response_model=BillRelatedBillsResponse,
)

bill_subjects = EndpointSpec(
    name="bill_subjects",
    path_template="/bill/{congress}/{billType}/{billNumber}/subjects",
    param_specs=_path_params_for_bill(),
    data_key=None,
    response_model=BillSubjectsResponse,
)

bill_summaries = EndpointSpec(
    name="bill_summaries",
    path_template="/bill/{congress}/{billType}/{billNumber}/summaries",
    param_specs=_path_params_for_bill(),
    data_key=None,
    response_model=BillSummariesResponse,
)

bill_titles = EndpointSpec(
    name="bill_titles",
    path_template="/bill/{congress}/{billType}/{billNumber}/titles",
    param_specs=_path_params_for_bill(),
    data_key=None,
    response_model=BillTitlesResponse,
)

register_spec(bill_actions)
register_spec(bill_amendments)
register_spec(bill_committees)
register_spec(bill_cosponsors)
register_spec(bill_relatedbills)
register_spec(bill_subjects)
register_spec(bill_summaries)
register_spec(bill_titles)

# Override/register `bill_text` with a response model so fetch_one returns a model
bill_text = EndpointSpec(
    name="bill_text",
    path_template="/bill/{congress}/{billType}/{billNumber}/text",
    param_specs=_path_params_for_bill(),
    data_key=None,
    response_model=BillTextResponse,
)
register_spec(bill_text)

# Additional summaries variants
bill_summaries_all = EndpointSpec(
    name="bill_summaries_all",
    path_template="/summaries",
    param_specs=[],
    data_key="summaries",
)

bill_summaries_by_congress = EndpointSpec(
    name="bill_summaries_by_congress",
    path_template="/summaries/{congress}",
    param_specs=[ParamSpec(name="congress", location=ParamLocation.PATH, required=True, source_field="congress")],
    data_key="summaries",
)

bill_summaries_by_type = EndpointSpec(
    name="bill_summaries_by_type",
    path_template="/summaries/{congress}/{billType}",
    param_specs=[
        ParamSpec(name="congress", location=ParamLocation.PATH, required=True, source_field="congress"),
        ParamSpec(name="billType", location=ParamLocation.PATH, required=True, source_field="type"),
    ],
    data_key="summaries",
)

# Register the new specs
register_spec(bill_list_all)
register_spec(bill_list_by_congress)
register_spec(bill_list_by_type)
register_spec(bill_details)
register_spec(bill_summaries_all)
register_spec(bill_summaries_by_congress)
register_spec(bill_summaries_by_type)

__all__.extend([
    "bill_list_all",
    "bill_list_by_congress",
    "bill_list_by_type",
    "bill_details",
    "bill_actions",
    "bill_amendments",
    "bill_committees",
    "bill_cosponsors",
    "bill_relatedbills",
    "bill_subjects",
    "bill_summaries",
    "bill_text",
    "bill_titles",
    "bill_summaries_all",
    "bill_summaries_by_congress",
    "bill_summaries_by_type",
])

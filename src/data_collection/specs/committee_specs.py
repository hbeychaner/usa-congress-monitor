from src.data_collection.endpoint_registry import (
    EndpointSpec,
    ParamLocation,
    ParamSpec,
    get_spec,
    register_spec,
    register_specs,
)
from src.models.bills import Committee
from src.models.other_models import (
    BillListItem,
    CommitteeListItem,
    CommitteeMeetingListItem,
    CommitteePrintListItem,
    CommitteeReportListItem,
    NominationListItem,
)

# Basic committee list/item specs
list_spec = EndpointSpec(
    name="committee_list",
    path_template="/committee",
    param_specs=[],
    data_key="committees",
    response_model=CommitteeListItem,
)

item_spec = EndpointSpec(
    name="committee_item",
    path_template="/committee/{chamber}/{committee_code}",
    param_specs=[
        ParamSpec(
            name="chamber",
            location=ParamLocation.PATH,
            required=True,
            source_field="chamber",
        ),
        ParamSpec(
            name="committee_code",
            location=ParamLocation.PATH,
            required=True,
            source_field="system_code",
            extract_from_url_segment="committee",
        ),
    ],
    data_key=None,
    unwrap_key="committee",
    response_model=Committee,
)

register_specs(list_spec, item_spec)


# Additional endpoints (reports/meetings/prints) return lists under specific keys
committee_reports = EndpointSpec(
    name="committee_reports",
    path_template="/committee/{chamber}/{committee_code}/reports",
    param_specs=item_spec.param_specs,
    data_key="committeeReports",
    response_model=CommitteeReportListItem,
)

committee_meetings = EndpointSpec(
    name="committee_meetings",
    path_template="/committee/{chamber}/{committee_code}/meetings",
    param_specs=item_spec.param_specs,
    data_key="committeeMeetings",
    response_model=CommitteeMeetingListItem,
)

committee_prints = EndpointSpec(
    name="committee_prints",
    path_template="/committee/{chamber}/{committee_code}/prints",
    param_specs=item_spec.param_specs,
    data_key="committeePrints",
    response_model=CommitteePrintListItem,
)

register_spec(committee_reports)
register_spec(committee_meetings)
register_spec(committee_prints)

# Committee-specific lists for bills and nominations
committee_bills = EndpointSpec(
    name="committee_bills",
    path_template="/committee/{chamber}/{committee_code}/bills",
    param_specs=item_spec.param_specs,
    data_key="bills",
    response_model=BillListItem,
)

committee_nominations = EndpointSpec(
    name="committee_nominations",
    path_template="/committee/{chamber}/{committee_code}/nominations",
    param_specs=item_spec.param_specs,
    data_key="nominations",
    response_model=NominationListItem,
)

register_spec(committee_bills)
register_spec(committee_nominations)


COMMITTEE_LIST_SPEC = get_spec("committee_list")
COMMITTEE_ITEM_SPEC = get_spec("committee_item")

__all__ = ["COMMITTEE_LIST_SPEC", "COMMITTEE_ITEM_SPEC"]

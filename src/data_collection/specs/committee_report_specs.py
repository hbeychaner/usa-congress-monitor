from src.data_collection.endpoint_registry import get_spec, register_from_model
from src.models.bills import CommitteeReport
from src.models.other_models import CommitteeReportListItem

# committee-report list and item
register_from_model(
    resource_name="committee_report",
    path_root="/committee-report",
    list_model=CommitteeReportListItem,
    item_model=CommitteeReport,
    data_key="reports",
    # use the URL tail (e.g. "119/HRPT/1") as the item path parameter
    # the client will extract this from the list `url` and lowercase it
    id_param_name="slug",
)

COMMITTEE_REPORT_LIST_SPEC = get_spec("committee_report_list")
COMMITTEE_REPORT_ITEM_SPEC = get_spec("committee_report_item")

# The API path uses hyphens ("committee-report") while our resource_name
# uses an underscore; ensure URL-extraction matches the API path.
COMMITTEE_REPORT_ITEM_SPEC.param_specs[0].extract_from_url_segment = "committee-report"

__all__ = ["COMMITTEE_REPORT_LIST_SPEC", "COMMITTEE_REPORT_ITEM_SPEC"]

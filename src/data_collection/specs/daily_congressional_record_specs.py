from src.data_collection.endpoint_registry import (
    EndpointSpec,
    ParamLocation,
    ParamSpec,
    get_spec,
    register_specs,
)
from src.models.other_models import DailyCongressionalRecordIssue

# daily-congressional-record list endpoint
list_spec = EndpointSpec(
    name="daily_congressional_record_list",
    path_template="/daily-congressional-record",
    param_specs=[],
    data_key="dailyCongressionalRecord",
    response_model=DailyCongressionalRecordIssue,
)

# item endpoint: /daily-congressional-record/{volumeNumber}/{issueNumber}
item_spec = EndpointSpec(
    name="daily_congressional_record_item",
    path_template="/daily-congressional-record/{volumeNumber}/{issueNumber}",
    param_specs=[
        ParamSpec(
            name="volumeNumber",
            location=ParamLocation.PATH,
            required=True,
            source_field="volume_number",
        ),
        ParamSpec(
            name="issueNumber",
            location=ParamLocation.PATH,
            required=True,
            source_field="issue_number",
        ),
    ],
    data_key=None,
    unwrap_key="issue",
    response_model=DailyCongressionalRecordIssue,
)

register_specs(list_spec, item_spec)

DAILY_CONGRESSIONAL_RECORD_LIST_SPEC = get_spec("daily_congressional_record_list")
DAILY_CONGRESSIONAL_RECORD_ITEM_SPEC = get_spec("daily_congressional_record_item")

__all__ = [
    "DAILY_CONGRESSIONAL_RECORD_LIST_SPEC",
    "DAILY_CONGRESSIONAL_RECORD_ITEM_SPEC",
]

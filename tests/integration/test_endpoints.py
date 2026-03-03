import os
import time
from typing import Any, Mapping, Type

import pytest
from requests import HTTPError

from src.data_collection.client import CDGClient
from src.data_collection.endpoints.amendment import (
    get_amendments_metadata,
    get_amendments_metadata_paginated,
)
from src.data_collection.endpoints.bound_congressional_record import get_bound_congressional_records
from src.data_collection.endpoints.committee import get_committees
from src.data_collection.endpoints.committee_meeting import get_committee_meetings
from src.data_collection.endpoints.committee_print import get_committee_prints
from src.data_collection.endpoints.committee_report import get_committee_reports
from src.data_collection.endpoints.congressional_record import get_congressional_records
from src.data_collection.endpoints.congress import get_congress_details, get_current_congress
from src.data_collection.endpoints.crs_report import get_crs_reports
from src.data_collection.endpoints.daily_congressional_record import get_daily_congressional_records
from src.data_collection.endpoints.hearing import get_hearings
from src.data_collection.endpoints.house_communication import get_house_communications
from src.data_collection.endpoints.house_requirement import get_house_requirements
from src.data_collection.endpoints.house_roll_call_vote import get_house_roll_call_votes
from src.data_collection.endpoints.bill import get_bills_metadata, get_bills_metadata_by_date
from src.data_collection.endpoints.law import get_laws, get_laws_metadata
from src.data_collection.endpoints.member import get_members_list
from src.data_collection.endpoints.nomination import get_nominations
from src.data_collection.endpoints.senate_communication import get_senate_communications
from src.data_collection.endpoints.summaries import get_summaries
from src.data_collection.endpoints.treaty import get_treaties
from src.data_collection.data_types import CongressDataType
from src.models.communications import (
    HouseCommunicationListItem,
    HouseRequirementListItem,
    SenateCommunicationListItem,
)
from src.models.committees import (
    CommitteeListItem,
    CommitteeMeetingListItem,
    CommitteePrintListItem,
    CommitteeReportListItem,
    HearingListItem,
)
from src.models.legislation import (
    AmendmentListItem,
    BillListItem,
    HouseRollCallVoteListItem,
    LawListItem,
    TreatyListItem,
)
from src.models.nominations import NominationListItem
from src.models.people_lists import MemberListItem
from src.models.records import (
    BoundCongressionalRecordListItem,
    CongressionalRecordIssue,
    DailyCongressionalRecordIssue,
)
from src.models.reports import BillSummaryListItem, CRSReportListItem


@pytest.fixture(scope="module")
def client():
    api_key = os.getenv("CONGRESS_API_KEY", "")
    if not api_key:
        pytest.skip("No API key set in environment")
    return CDGClient(api_key=api_key)


def get_response_with_retries(func, *args, retries: int = 3, **kwargs) -> Mapping[str, Any]:
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except HTTPError as exc:
            status = getattr(exc.response, "status_code", None)
            if status is not None and status >= 500 and attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            pytest.skip(f"Upstream API unavailable (status {status}).")
    raise RuntimeError("Failed to retrieve response after retries.")


def get_first_item(response: Mapping[str, Any], key: CongressDataType) -> Any:
    items = response.get(str(key), [])
    assert items, f"No items returned for key '{key}'"
    return items[0]


def assert_model_covers_keys(model_cls: Type[Any], data: Mapping[str, Any]) -> None:
    field_keys = set(model_cls.model_fields.keys())
    for field in model_cls.model_fields.values():
        alias = getattr(field, "alias", None)
        if alias:
            field_keys.add(alias)
    missing = set(data.keys()) - field_keys
    assert not missing, f"{model_cls.__name__} missing fields: {sorted(missing)}"


def test_member_endpoint(client):
    response = get_response_with_retries(get_members_list, client, pageSize=1)
    member_data = get_first_item(response, CongressDataType.MEMBERS)
    assert_model_covers_keys(MemberListItem, member_data)
    member_obj = MemberListItem(**member_data)
    assert member_obj.bioguide_id


def test_amendment_endpoint(client):
    response = get_response_with_retries(get_amendments_metadata_paginated, client, pageSize=1)
    amendment_data = get_first_item(response, CongressDataType.AMENDMENTS)
    assert_model_covers_keys(AmendmentListItem, amendment_data)
    amendment_obj = AmendmentListItem(**amendment_data)
    assert amendment_obj.number is not None


def test_amendment_metadata_endpoint(client):
    results, _, _ = get_response_with_retries(
        get_amendments_metadata,
        client,
        from_date="2025-01-01",
        to_date="2025-01-05",
    )
    assert results is not None


def test_bill_metadata_by_date_endpoint(client):
    results, _, _ = get_response_with_retries(
        get_bills_metadata_by_date,
        client,
        from_date="2025-01-01",
        to_date="2025-01-05",
    )
    assert results is not None


def test_bill_endpoint(client):
    response = get_response_with_retries(get_bills_metadata, client, pageSize=1)
    bill_data = get_first_item(response, CongressDataType.BILLS)
    assert_model_covers_keys(BillListItem, bill_data)
    bill_obj = BillListItem(**bill_data)
    assert bill_obj.number is not None


def test_committee_endpoint(client):
    response = get_response_with_retries(get_committees, client, pageSize=1)
    committee_data = get_first_item(response, CongressDataType.COMMITTEES)
    assert_model_covers_keys(CommitteeListItem, committee_data)
    committee_obj = CommitteeListItem(**committee_data)
    assert committee_obj.system_code


def test_law_endpoint(client):
    response = get_response_with_retries(get_laws, client, congress=118, pageSize=1)
    law_data = get_first_item(response, CongressDataType.LAWS)
    assert_model_covers_keys(LawListItem, law_data)
    law_obj = LawListItem(**law_data)
    assert law_obj.number is not None


def test_law_metadata_endpoint(client):
    results, _, _ = get_response_with_retries(get_laws_metadata, client, congress=118, offset=0)
    assert results is not None


def test_committee_report_endpoint(client):
    response = get_response_with_retries(get_committee_reports, client, pageSize=1)
    report_data = get_first_item(response, CongressDataType.REPORTS)
    assert_model_covers_keys(CommitteeReportListItem, report_data)
    report_obj = CommitteeReportListItem(**report_data)
    assert report_obj.citation


def test_committee_print_endpoint(client):
    response = get_response_with_retries(get_committee_prints, client)
    print_data = get_first_item(response, CongressDataType.COMMITTEE_PRINTS)
    assert_model_covers_keys(CommitteePrintListItem, print_data)
    print_obj = CommitteePrintListItem(**print_data)
    assert print_obj.jacket_number is not None


def test_committee_meeting_endpoint(client):
    response = get_response_with_retries(get_committee_meetings, client, pageSize=1)
    meeting_data = get_first_item(response, CongressDataType.COMMITTEE_MEETINGS)
    assert_model_covers_keys(CommitteeMeetingListItem, meeting_data)
    meeting_obj = CommitteeMeetingListItem(**meeting_data)
    assert meeting_obj.event_id is not None


def test_hearing_endpoint(client):
    response = get_response_with_retries(get_hearings, client, pageSize=1)
    hearing_data = get_first_item(response, CongressDataType.HEARINGS)
    assert_model_covers_keys(HearingListItem, hearing_data)
    hearing_obj = HearingListItem(**hearing_data)
    assert hearing_obj.jacket_number is not None


def test_house_communication_endpoint(client):
    response = get_response_with_retries(get_house_communications, client, pageSize=1)
    comm_data = get_first_item(response, CongressDataType.HOUSE_COMMUNICATIONS)
    assert_model_covers_keys(HouseCommunicationListItem, comm_data)
    comm_obj = HouseCommunicationListItem(**comm_data)
    assert comm_obj.number is not None


def test_house_requirement_endpoint(client):
    response = get_response_with_retries(get_house_requirements, client, pageSize=1)
    req_data = get_first_item(response, CongressDataType.HOUSE_REQUIREMENTS)
    assert_model_covers_keys(HouseRequirementListItem, req_data)
    req_obj = HouseRequirementListItem(**req_data)
    assert req_obj.number is not None


def test_house_roll_call_vote_endpoint(client):
    response = get_response_with_retries(get_house_roll_call_votes, client, pageSize=1)
    vote_data = get_first_item(response, CongressDataType.HOUSE_ROLL_CALL_VOTES)
    assert_model_covers_keys(HouseRollCallVoteListItem, vote_data)
    vote_obj = HouseRollCallVoteListItem(**vote_data)
    assert vote_obj.identifier


def test_senate_communication_endpoint(client):
    response = get_response_with_retries(get_senate_communications, client, pageSize=1)
    comm_data = get_first_item(response, CongressDataType.SENATE_COMMUNICATIONS)
    assert_model_covers_keys(SenateCommunicationListItem, comm_data)
    comm_obj = SenateCommunicationListItem(**comm_data)
    assert comm_obj.number is not None


def test_nomination_endpoint(client):
    response = get_response_with_retries(get_nominations, client, pageSize=1)
    nomination_data = get_first_item(response, CongressDataType.NOMINATIONS)
    assert_model_covers_keys(NominationListItem, nomination_data)
    nomination_obj = NominationListItem(**nomination_data)
    assert nomination_obj.number is not None


def test_crs_report_endpoint(client):
    response = get_response_with_retries(get_crs_reports, client, pageSize=1)
    report_data = get_first_item(response, CongressDataType.CRS_REPORTS)
    assert_model_covers_keys(CRSReportListItem, report_data)
    report_obj = CRSReportListItem(**report_data)
    assert report_obj.id


def test_summaries_endpoint(client):
    response = get_response_with_retries(get_summaries, client, pageSize=1)
    summary_data = get_first_item(response, CongressDataType.SUMMARIES)
    assert_model_covers_keys(BillSummaryListItem, summary_data)
    summary_obj = BillSummaryListItem(**summary_data)
    assert summary_obj.bill


def test_treaty_endpoint(client):
    response = get_response_with_retries(get_treaties, client, pageSize=1)
    treaty_data = get_first_item(response, CongressDataType.TREATIES)
    assert_model_covers_keys(TreatyListItem, treaty_data)
    treaty_obj = TreatyListItem(**treaty_data)
    assert treaty_obj.number is not None


def test_bound_congressional_record_endpoint(client):
    response = get_response_with_retries(get_bound_congressional_records, client, pageSize=1)
    record_data = get_first_item(response, CongressDataType.BOUND_CONGRESSIONAL_RECORD)
    assert_model_covers_keys(BoundCongressionalRecordListItem, record_data)
    record_obj = BoundCongressionalRecordListItem(**record_data)
    assert record_obj.date is not None


def test_daily_congressional_record_endpoint(client):
    response = get_response_with_retries(get_daily_congressional_records, client, pageSize=1)
    record_data = get_first_item(response, CongressDataType.DAILY_CONGRESSIONAL_RECORD)
    assert_model_covers_keys(DailyCongressionalRecordIssue, record_data)
    record_obj = DailyCongressionalRecordIssue(**record_data)
    assert record_obj.issue_number


def test_congressional_record_endpoint(client):
    response = get_response_with_retries(
        get_congressional_records, client, year=2022, month=6, day=28
    )
    issues = response.get("Results", {}).get("Issues", [])
    assert issues, "No congressional record issues returned from API"
    issue_obj = CongressionalRecordIssue(**issues[0])
    assert issue_obj.id is not None


def test_congress_endpoints(client):
    response = get_response_with_retries(get_current_congress, client)
    congress_number = response.get("congress", {}).get("number")
    assert congress_number is not None

    details = get_response_with_retries(get_congress_details, client, congress=congress_number)
    assert details.get("congress", {}).get("number") == congress_number

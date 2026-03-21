import src.data_collection.specs.committee_specs  # registers committee specs
import src.data_collection.specs.nomination_specs  # registers nomination specs
from src.models.other_models import BillListItem as _BillListItem
from src.models.other_models import NominationListItem as _NominationListItem

from src.data_collection.endpoint_registry import get_spec
from src.models.other_models import (
    CommitteeListItem,
    CommitteeReportListItem,
    CommitteeMeetingListItem,
    CommitteePrintListItem,
    NominationListItem,
)


def test_committee_specs_registered():
    list_spec = get_spec("committee_list")
    item_spec = get_spec("committee_item")
    assert list_spec is not None
    assert item_spec is not None
    assert list_spec.response_model is CommitteeListItem


def test_committee_sub_specs():
    reports = get_spec("committee_reports")
    meetings = get_spec("committee_meetings")
    prints = get_spec("committee_prints")
    assert reports.response_model is CommitteeReportListItem
    assert meetings.response_model is CommitteeMeetingListItem
    assert prints.response_model is CommitteePrintListItem
    bills = get_spec("committee_bills")
    noms = get_spec("committee_nominations")
    assert bills.response_model is _BillListItem
    assert noms.response_model is _NominationListItem


def test_nomination_specs_registered():
    n_list = get_spec("nomination_list")
    n_item = get_spec("nomination_item")
    assert n_list is not None
    assert n_item is not None
    assert n_list.response_model is NominationListItem

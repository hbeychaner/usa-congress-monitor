import pytest
from datetime import datetime

from src.models.other_models import MemberListItem, BillListItem
from src.models.shared import EntityBase


def test_build_id_member_bioguide():
    m = MemberListItem(bioguideId="A123")
    assert m.build_id() == "member:A123"


def test_build_id_bill_composition():
    b = BillListItem(congress=110, type="hconres", number="10")
    assert b.build_id() == "bill:110:hconres:10"


def test_build_id_from_url_when_no_congress_number():
    url = "https://api.congress.gov/v3/bill/110/hconres/10?format=json"
    b = BillListItem(url=url)
    # URL parsing should produce the canonical bill id (query stripped)
    assert b.build_id() == "bill:110:hconres:10"


def test_build_id_raises_when_unavailable():
    class Minimal(EntityBase):
        pass

    m = Minimal()
    with pytest.raises(ValueError):
        m.build_id()

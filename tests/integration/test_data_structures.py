import os
import pytest
from src.data_collection.client import CDGClient
from src.data_collection.endpoints.member import get_members_list
from src.models.people_lists import MemberListItem
from src.data_collection.data_types import CongressDataType

@pytest.fixture(scope="module")
def client():
    api_key = os.getenv("CONGRESS_API_KEY","")
    if not api_key:
        pytest.skip("No API key set in environment")
    return CDGClient(api_key=api_key)

def test_member_list_item_parsing(client):
    response = get_members_list(client, pageSize=1)
    members = response.get(str(CongressDataType.MEMBERS), [])
    assert members, "No members returned from API"
    member_obj = MemberListItem(**members[0])
    assert member_obj.bioguide_id

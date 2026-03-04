import pytest
from settings import CONGRESS_API_KEY
from src.data_collection.client import CDGClient
from src.data_collection.endpoints.members import get_members_list
from src.models.people_lists import MemberListItem
from src.models.data_types import CongressDataType


@pytest.fixture(scope="module")
def client():
    if not CONGRESS_API_KEY:
        pytest.skip("No API key set in environment")
    return CDGClient(api_key=CONGRESS_API_KEY)


def test_member_list_item_parsing(client):
    response = get_members_list(client, limit=1)
    members = response.get(str(CongressDataType.MEMBERS), [])
    assert members, "No members returned from API"
    member_obj = MemberListItem(**members[0])
    assert member_obj.bioguide_id

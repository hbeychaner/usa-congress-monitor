from fastapi import APIRouter, HTTPException, Query

from cdm.backend.services.member_service import get_member_profile, list_members
from cdm.contracts.api import MemberProfileResponse, MembersResponse

router = APIRouter(prefix="/members", tags=["members"])


@router.get("", response_model=MembersResponse)
def get_members(
    query: str | None = Query(default=None),
    state: str | None = Query(default=None),
    chamber: str | None = Query(default=None),
    party: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=10, le=100),
) -> MembersResponse:
    return list_members(query, state, chamber, party, page, limit)


@router.get("/{bioguide_id}", response_model=MemberProfileResponse)
def get_member(bioguide_id: str) -> MemberProfileResponse:
    try:
        return get_member_profile(bioguide_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

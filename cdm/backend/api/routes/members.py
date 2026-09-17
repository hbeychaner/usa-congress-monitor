from fastapi import APIRouter, HTTPException, Query

from cdm.backend.services.member_service import (
    get_member_profile,
    list_member_activity,
    list_members,
)
from cdm.backend.services.topic_service import get_member_topics
from cdm.contracts.api import (
    MemberActivityResponse,
    MemberProfileResponse,
    MembersResponse,
    MemberTopicsResponse,
)

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


@router.get("/{bioguide_id}/activity", response_model=MemberActivityResponse)
def get_member_activity(
    bioguide_id: str,
    types: str | None = Query(default=None, description="Comma-separated document types"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=5, le=100),
) -> MemberActivityResponse:
    return list_member_activity(bioguide_id, types, page, limit)


@router.get("/{bioguide_id}/topics", response_model=MemberTopicsResponse)
def member_topics(bioguide_id: str) -> MemberTopicsResponse:
    return get_member_topics(bioguide_id)

from typing import Annotated

from fastapi import APIRouter, Query

from cdm.backend.dependencies import (
    GraphServiceDep,
    MemberServiceDep,
    TopicServiceDep,
)
from cdm.contracts.api import (
    ErrorResponse,
    MemberActivityResponse,
    MemberProfileResponse,
    MembersResponse,
    MemberTopicsResponse,
    SimilarMembersResponse,
)
from cdm.graph.models import Signal

router = APIRouter(prefix="/members", tags=["members"])


@router.get("", response_model=MembersResponse)
def get_members(
    service: MemberServiceDep,
    query: str | None = Query(default=None, max_length=200),
    state: str | None = Query(default=None, max_length=200),
    chamber: str | None = Query(default=None, max_length=200),
    party: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=10, le=100),
) -> MembersResponse:
    return service.list_members(query, state, chamber, party, page, limit)


@router.get(
    "/{bioguide_id}",
    response_model=MemberProfileResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_member(bioguide_id: str, service: MemberServiceDep) -> MemberProfileResponse:
    return service.get_profile(bioguide_id)


@router.get("/{bioguide_id}/activity", response_model=MemberActivityResponse)
def get_member_activity(
    bioguide_id: str,
    service: MemberServiceDep,
    types: str | None = Query(
        default=None,
        max_length=200,
        description="Comma-separated document types: bill,amendment",
    ),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=5, le=100),
) -> MemberActivityResponse:
    return service.list_activity(bioguide_id, types, page, limit)


@router.get("/{bioguide_id}/topics", response_model=MemberTopicsResponse)
def member_topics(bioguide_id: str, service: TopicServiceDep) -> MemberTopicsResponse:
    return service.get_member_topics(bioguide_id)


@router.get("/{bioguide_id}/similar", response_model=SimilarMembersResponse)
def similar_members(
    bioguide_id: str,
    graph: GraphServiceDep,
    signal: Annotated[Signal, Query()] = Signal.COLLABORATION,
    congress: int | None = Query(default=None, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
) -> SimilarMembersResponse:
    return graph.similar(bioguide_id, signal, congress, limit)

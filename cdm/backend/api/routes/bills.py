from fastapi import APIRouter, Query

from cdm.backend.dependencies import (
    BillServiceDep,
    SimilarBillServiceDep,
    TopicServiceDep,
    VoteServiceDep,
)
from cdm.contracts.api import (
    BillDetailResponse,
    BillsResponse,
    BillTopicsResponse,
    BillVotesResponse,
    SimilarBillsResponse,
)

router = APIRouter(prefix="/bills", tags=["bills"])


@router.get("/recent", response_model=BillsResponse)
def recent_bills(
    service: BillServiceDep,
    limit: int = Query(default=50, ge=10, le=100),
    page: int = Query(default=1, ge=1),
    query: str | None = Query(default=None, max_length=200),
    congress: int | None = Query(default=None, ge=1, le=200),
    bill_type: str | None = Query(default=None, max_length=20),
    chamber: str | None = Query(default=None, pattern="^(House|Senate)$"),
    subject: str | None = Query(default=None, max_length=200),
) -> BillsResponse:
    return service.list_recent(
        limit, page, query, congress, bill_type, chamber, subject
    )


@router.get("/{bill_id}", response_model=BillDetailResponse)
def bill_detail(bill_id: str, service: BillServiceDep) -> BillDetailResponse:
    return service.get(bill_id)


@router.get("/{bill_id}/votes", response_model=BillVotesResponse)
def bill_votes(bill_id: str, service: VoteServiceDep) -> BillVotesResponse:
    return service.for_bill(bill_id)


@router.get("/{bill_id}/topics", response_model=BillTopicsResponse)
def bill_topics(bill_id: str, service: TopicServiceDep) -> BillTopicsResponse:
    return service.get_bill_topics(bill_id)


@router.get("/{bill_id}/similar", response_model=SimilarBillsResponse)
def similar_bills(
    bill_id: str,
    service: SimilarBillServiceDep,
    limit: int = Query(default=10, ge=1, le=50),
) -> SimilarBillsResponse:
    return service.similar(bill_id, limit)

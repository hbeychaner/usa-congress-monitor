from fastapi import APIRouter, Query

from cdm.backend.services.bill_service import get_bill, list_recent_bills
from cdm.contracts.api import BillDetailResponse, BillsResponse

router = APIRouter(prefix="/bills", tags=["bills"])


@router.get("/recent", response_model=BillsResponse)
def recent_bills(
    limit: int = Query(default=50, ge=10, le=100),
    page: int = Query(default=1, ge=1),
    query: str | None = Query(default=None, max_length=200),
    congress: int | None = Query(default=None, ge=1, le=200),
    bill_type: str | None = Query(default=None, max_length=20),
    chamber: str | None = Query(default=None, pattern="^(House|Senate)$"),
) -> BillsResponse:
    return list_recent_bills(limit, page, query, congress, bill_type, chamber)


@router.get("/{bill_id}", response_model=BillDetailResponse)
def bill_detail(bill_id: str) -> BillDetailResponse:
    return get_bill(bill_id)

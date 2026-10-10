from fastapi import APIRouter, Query

from cdm.backend.dependencies import CommitteeServiceDep
from cdm.contracts.api import CommitteeDetailResponse

router = APIRouter(prefix="/committees", tags=["committees"])


@router.get("/{system_code}", response_model=CommitteeDetailResponse)
def committee_detail(
    system_code: str,
    service: CommitteeServiceDep,
    limit: int = Query(default=50, ge=10, le=100),
    page: int = Query(default=1, ge=1),
) -> CommitteeDetailResponse:
    return service.detail(system_code, page, limit)

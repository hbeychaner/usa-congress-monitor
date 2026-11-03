from fastapi import APIRouter, Query

from cdm.backend.dependencies import SearchServiceDep
from cdm.contracts.api import SearchResponse

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
def search(
    service: SearchServiceDep,
    q: str = Query(min_length=1, max_length=200),
    types: str = Query(default="member,state,bill", max_length=200),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Maximum results per selected type; groups are not globally ranked.",
    ),
) -> SearchResponse:
    return service.search(q, types, limit)

from fastapi import APIRouter, Query

from cdm.contracts.api import SearchResponse
from cdm.backend.services.search_service import search_entities

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
def search(
    q: str = Query(min_length=1),
    types: str = Query(default="member,state,bill"),
    limit: int = Query(default=20, ge=1, le=100),
) -> SearchResponse:
    return search_entities(q, types, limit)

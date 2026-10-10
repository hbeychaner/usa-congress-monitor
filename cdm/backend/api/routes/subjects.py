from fastapi import APIRouter, Query

from cdm.backend.dependencies import SubjectServiceDep
from cdm.contracts.api import PolicyAreaTrendsResponse, SubjectsResponse

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.get("", response_model=SubjectsResponse)
def subjects_list(
    service: SubjectServiceDep,
    congress: int | None = Query(default=None, ge=1, le=200),
    size: int = Query(default=100, ge=10, le=500),
) -> SubjectsResponse:
    return service.list_subjects(congress, size)


@router.get("/policy-area-trends", response_model=PolicyAreaTrendsResponse)
def policy_area_trends(
    service: SubjectServiceDep,
    size: int = Query(default=10, ge=1, le=32),
    start_year: int | None = Query(default=None, ge=1900, le=2100),
) -> PolicyAreaTrendsResponse:
    return service.list_policy_area_trends(size=size, start_year=start_year)

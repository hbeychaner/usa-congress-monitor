from fastapi import APIRouter, Query

from cdm.backend.services.subject_service import list_subjects
from cdm.contracts.api import SubjectsResponse

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.get("", response_model=SubjectsResponse)
def subjects_list(
    congress: int | None = Query(default=None, ge=1, le=200),
    size: int = Query(default=100, ge=10, le=500),
) -> SubjectsResponse:
    return list_subjects(congress, size)

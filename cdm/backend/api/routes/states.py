from fastapi import APIRouter, Query

from cdm.backend.dependencies import StateServiceDep
from cdm.contracts.api import StateSummary, StateTimelineResponse

router = APIRouter(prefix="/states", tags=["states"])


@router.get("", response_model=list[StateSummary])
def get_states(service: StateServiceDep) -> list[StateSummary]:
    return service.list_states()


@router.get("/{state_code}/timeline", response_model=StateTimelineResponse)
def get_timeline(
    state_code: str,
    service: StateServiceDep,
    from_congress: int | None = Query(default=None),
    to_congress: int | None = Query(default=None),
) -> StateTimelineResponse:
    return service.get_timeline(state_code, from_congress, to_congress)


@router.get("/{state_code}/districts")
def get_districts(state_code: str, service: StateServiceDep) -> dict:
    return service.get_districts(state_code)

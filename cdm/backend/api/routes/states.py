from fastapi import APIRouter, Query

from cdm.backend.services.state_service import (
    get_state_districts,
    get_state_timeline,
    list_states,
)
from cdm.contracts.api import StateSummary, StateTimelineResponse

router = APIRouter(prefix="/states", tags=["states"])


@router.get("", response_model=list[StateSummary])
def get_states() -> list[StateSummary]:
    return list_states()


@router.get("/{state_code}/timeline", response_model=StateTimelineResponse)
def get_timeline(
    state_code: str,
    from_congress: int | None = Query(default=None),
    to_congress: int | None = Query(default=None),
) -> StateTimelineResponse:
    return get_state_timeline(state_code, from_congress, to_congress)


@router.get("/{state_code}/districts")
def get_districts(state_code: str) -> dict:
    return get_state_districts(state_code.upper())

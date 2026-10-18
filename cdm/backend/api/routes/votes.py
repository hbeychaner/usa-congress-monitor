from fastapi import APIRouter, HTTPException

from cdm.backend.dependencies import VoteBreakdownServiceDep
from cdm.contracts.api import VoteBreakdownResponse

router = APIRouter(prefix="/votes", tags=["votes"])


@router.get("/{vote_id}/breakdown", response_model=VoteBreakdownResponse)
def vote_breakdown(
    vote_id: str, service: VoteBreakdownServiceDep
) -> VoteBreakdownResponse:
    result = service.for_vote(vote_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Roll call not found")
    return result

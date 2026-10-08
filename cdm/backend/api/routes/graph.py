from fastapi import APIRouter, Query

from cdm.backend.services.neighborhood_service import (
    NeighborhoodQuery,
    NeighborhoodService,
)
from cdm.contracts.api import NeighborhoodResponse
from cdm.graph.models import PartyGroup, Signal
from cdm.ingest.voteview import Chamber

router = APIRouter(prefix="/graph", tags=["graph"])
service = NeighborhoodService()


@router.get("/neighborhood", response_model=NeighborhoodResponse)
def neighborhood(
    member: list[str] = Query(min_length=1, max_length=5),
    collaboration_weight: float = Query(default=1.0, ge=0, le=1),
    voting_weight: float = Query(default=0.6, ge=0, le=1),
    topic_weight: float = Query(default=0.3, ge=0, le=1),
    congress: int | None = Query(default=None, ge=1),
    limit: int = Query(default=15, ge=1, le=50),
    party: list[PartyGroup] = Query(default=[]),
    chamber: Chamber | None = None,
) -> NeighborhoodResponse:
    return service.neighborhood(
        NeighborhoodQuery(
            seeds=member,
            weights={
                Signal.COLLABORATION: collaboration_weight,
                Signal.VOTING: voting_weight,
                Signal.TOPIC: topic_weight,
            },
            congress=congress,
            limit=limit,
            parties=set(party),
            chamber=chamber,
        )
    )

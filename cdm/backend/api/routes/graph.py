from typing import Annotated

from fastapi import APIRouter, Query

from cdm.backend.dependencies import NeighborhoodServiceDep
from cdm.backend.services.neighborhood_service import NeighborhoodQuery
from cdm.contracts.api import NeighborhoodResponse
from cdm.graph.models import PartyGroup, Signal
from cdm.ingest.voteview import Chamber

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/neighborhood", response_model=NeighborhoodResponse)
def neighborhood(
    service: NeighborhoodServiceDep,
    member: Annotated[list[str], Query(min_length=1, max_length=5)],
    collaboration_weight: float = Query(default=1.0, ge=0, le=1),
    voting_weight: float = Query(default=0.6, ge=0, le=1),
    topic_weight: float = Query(default=0.3, ge=0, le=1),
    congress: int | None = Query(default=None, ge=1),
    limit: int = Query(default=15, ge=1, le=50),
    party: Annotated[list[PartyGroup] | None, Query()] = None,
    chamber: Chamber | None = None,
    include_topics: bool = False,
    topics_per_member: int = Query(default=3, ge=1, le=8),
    include_subjects: bool = False,
    subjects_per_member: int = Query(default=3, ge=1, le=8),
    include_metasubjects: bool = False,
    metasubjects_per_member: int = Query(default=3, ge=1, le=8),
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
            parties=set(party or []),
            chamber=chamber,
            include_topics=include_topics,
            topics_per_member=topics_per_member,
            include_subjects=include_subjects,
            subjects_per_member=subjects_per_member,
            include_metasubjects=include_metasubjects,
            metasubjects_per_member=metasubjects_per_member,
        )
    )

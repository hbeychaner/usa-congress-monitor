from fastapi import APIRouter, HTTPException

from cdm.backend.dependencies import PartyServiceDep
from cdm.contracts.api import PartiesResponse, PartyTopicResponse

router = APIRouter(prefix="/parties")


@router.get("", response_model=PartiesResponse)
def parties(service: PartyServiceDep, congress: int | None = None) -> PartiesResponse:
    return service.overview(congress)


@router.get("/topics/{topic_id}", response_model=PartyTopicResponse)
def party_topic(
    topic_id: int, congress: int, service: PartyServiceDep
) -> PartyTopicResponse:
    result = service.topic(congress, topic_id)
    if result is None:
        raise HTTPException(status_code=404, detail="No party analysis for this topic")
    return result

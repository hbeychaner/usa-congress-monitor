from fastapi import APIRouter, HTTPException

from cdm.backend.services.topic_service import get_topic, list_topics
from cdm.contracts.api import TopicDetailResponse, TopicsResponse

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("", response_model=TopicsResponse)
def topics_list() -> TopicsResponse:
    return list_topics()


@router.get("/{topic_id}", response_model=TopicDetailResponse)
def topic_detail(topic_id: int) -> TopicDetailResponse:
    detail = get_topic(topic_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="topic not found")
    return detail

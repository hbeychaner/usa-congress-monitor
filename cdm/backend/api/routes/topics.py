from fastapi import APIRouter, HTTPException

from cdm.backend.dependencies import TopicServiceDep
from cdm.contracts.api import (
    MetasubjectDetailResponse,
    MetasubjectsResponse,
    MetasubjectTrendsResponse,
    TopicDetailResponse,
    TopicsResponse,
    TopicTrendsResponse,
)

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("", response_model=TopicsResponse)
def topics_list(service: TopicServiceDep) -> TopicsResponse:
    return service.list_topics()


@router.get("/trends", response_model=TopicTrendsResponse)
def topic_trends(service: TopicServiceDep, size: int = 8) -> TopicTrendsResponse:
    return service.list_topic_trends(size=max(1, min(size, 25)))


@router.get("/metasubjects", response_model=MetasubjectsResponse)
def metasubjects_list(service: TopicServiceDep) -> MetasubjectsResponse:
    return service.list_metasubjects()


@router.get("/metasubjects/trends", response_model=MetasubjectTrendsResponse)
def metasubject_trends(service: TopicServiceDep) -> MetasubjectTrendsResponse:
    return service.list_metasubject_trends()


@router.get("/metasubjects/{metasubject_id}", response_model=MetasubjectDetailResponse)
def metasubject_detail(
    metasubject_id: int, service: TopicServiceDep
) -> MetasubjectDetailResponse:
    detail = service.get_metasubject(metasubject_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="metasubject not found")
    return detail


@router.get("/{topic_id}", response_model=TopicDetailResponse)
def topic_detail(
    topic_id: int, service: TopicServiceDep, bills: int = 20
) -> TopicDetailResponse:
    detail = service.get_topic(topic_id, top_bills=max(1, min(bills, 200)))
    if detail is None:
        raise HTTPException(status_code=404, detail="topic not found")
    return detail

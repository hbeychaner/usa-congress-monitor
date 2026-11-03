from fastapi import APIRouter, HTTPException

from cdm.backend.dependencies import AdminServiceDep, AnalyticsJobsDep
from cdm.contracts.api import (
    AdminIngestSnapshot,
    IngestProgressResponse,
    SystemStatusResponse,
    TopicTrainingStatus,
)
from cdm.graph.models import GraphBuildStatus
from cdm.jobs.analytics import (
    AnalysisBusy,
    AnalysisRequest,
    AnalysisSubmission,
    AnalyticsJobs,
    GraphRequest,
    PerspectiveRequest,
    TopicRequest,
)
from cdm.jobs.store import JobKind

router = APIRouter(prefix="/admin", tags=["admin"])


def _start[Status: TopicTrainingStatus | GraphBuildStatus](
    jobs: AnalyticsJobs, request: AnalysisRequest, schema: type[Status]
) -> Status:
    try:
        submission = jobs.submit(request)
    except AnalysisBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return jobs.status(request.kind, schema, job_id=submission.job_id).model_copy(
        update={"started": submission.started}
    )


@router.post("/analytics/{job_id}/cancel", response_model=AnalysisSubmission)
def cancel_analytics(job_id: str, jobs: AnalyticsJobsDep) -> AnalysisSubmission:
    try:
        return jobs.cancel(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/topic-training", response_model=TopicTrainingStatus)
def topic_training_status(jobs: AnalyticsJobsDep) -> TopicTrainingStatus:
    return jobs.status(JobKind.TOPIC_TRAINING, TopicTrainingStatus)


@router.post("/topic-training", response_model=TopicTrainingStatus)
def topic_training_start(jobs: AnalyticsJobsDep) -> TopicTrainingStatus:
    return _start(jobs, TopicRequest(), TopicTrainingStatus)


@router.get("/member-graph", response_model=GraphBuildStatus)
def member_graph_status(jobs: AnalyticsJobsDep) -> GraphBuildStatus:
    return jobs.status(JobKind.MEMBER_GRAPH, GraphBuildStatus)


@router.post("/member-graph", response_model=GraphBuildStatus)
def member_graph_build(jobs: AnalyticsJobsDep) -> GraphBuildStatus:
    return _start(jobs, GraphRequest(), GraphBuildStatus)


@router.get("/perspectives", response_model=GraphBuildStatus)
def perspectives_status(jobs: AnalyticsJobsDep) -> GraphBuildStatus:
    return jobs.status(JobKind.PERSPECTIVES, GraphBuildStatus)


@router.post("/perspectives", response_model=GraphBuildStatus)
def perspectives_build(jobs: AnalyticsJobsDep) -> GraphBuildStatus:
    return _start(jobs, PerspectiveRequest(top_topics=None), GraphBuildStatus)


@router.get("/ingest-progress", response_model=IngestProgressResponse)
def ingest_progress(service: AdminServiceDep) -> IngestProgressResponse:
    return service.get_ingest_progress()


@router.get("/ingest-snapshot", response_model=AdminIngestSnapshot)
def ingest_snapshot(service: AdminServiceDep) -> AdminIngestSnapshot:
    return service.get_admin_ingest_snapshot()


@router.get("/system-status", response_model=SystemStatusResponse)
def system_status(service: AdminServiceDep) -> SystemStatusResponse:
    return service.get_system_status()

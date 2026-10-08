from fastapi import APIRouter

from cdm.backend.services.admin_service import (
    get_admin_ingest_snapshot,
    get_ingest_progress,
    get_system_status,
)
from cdm.contracts.api import (
    AdminIngestSnapshot,
    IngestProgressResponse,
    SystemStatusResponse,
    TopicTrainingStatus,
)
from cdm.graph.runner import GraphBuildRunner, GraphBuildStatus
from cdm.utils.topic_training import read_status, start_training

router = APIRouter(prefix="/admin", tags=["admin"])
graph_runner = GraphBuildRunner()


@router.get("/topic-training", response_model=TopicTrainingStatus)
def topic_training_status() -> TopicTrainingStatus:
    return TopicTrainingStatus(**read_status())


@router.post("/topic-training", response_model=TopicTrainingStatus)
def topic_training_start() -> TopicTrainingStatus:
    return TopicTrainingStatus(**start_training())


@router.get("/member-graph", response_model=GraphBuildStatus)
def member_graph_status() -> GraphBuildStatus:
    return graph_runner.read()


@router.post("/member-graph", response_model=GraphBuildStatus)
def member_graph_build() -> GraphBuildStatus:
    return graph_runner.start()


@router.get("/ingest-progress", response_model=IngestProgressResponse)
def ingest_progress() -> IngestProgressResponse:
    return get_ingest_progress()


@router.get("/ingest-snapshot", response_model=AdminIngestSnapshot)
def ingest_snapshot() -> AdminIngestSnapshot:
    return get_admin_ingest_snapshot()


@router.get("/system-status", response_model=SystemStatusResponse)
def system_status() -> SystemStatusResponse:
    return get_system_status()

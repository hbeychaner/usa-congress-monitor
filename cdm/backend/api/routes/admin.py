from fastapi import APIRouter

from cdm.backend.dependencies import AdminServiceDep
from cdm.contracts.api import (
    AdminIngestSnapshot,
    IngestProgressResponse,
    SystemStatusResponse,
    TopicTrainingStatus,
)
from cdm.graph.runner import GraphBuildRunner, GraphBuildStatus
from cdm.perspectives.launcher import PerspectiveBuildLauncher
from cdm.utils.topic_training import read_status, start_training

router = APIRouter(prefix="/admin", tags=["admin"])
graph_runner = GraphBuildRunner()
perspective_launcher = PerspectiveBuildLauncher()


@router.get("/topic-training", response_model=TopicTrainingStatus)
def topic_training_status() -> TopicTrainingStatus:
    return read_status()


@router.post("/topic-training", response_model=TopicTrainingStatus)
def topic_training_start() -> TopicTrainingStatus:
    return start_training()


@router.get("/member-graph", response_model=GraphBuildStatus)
def member_graph_status() -> GraphBuildStatus:
    return graph_runner.read()


@router.post("/member-graph", response_model=GraphBuildStatus)
def member_graph_build() -> GraphBuildStatus:
    return graph_runner.start()


@router.get("/perspectives", response_model=GraphBuildStatus)
def perspectives_status() -> GraphBuildStatus:
    return perspective_launcher.read()


@router.post("/perspectives", response_model=GraphBuildStatus)
def perspectives_build() -> GraphBuildStatus:
    return perspective_launcher.start()


@router.get("/ingest-progress", response_model=IngestProgressResponse)
def ingest_progress(service: AdminServiceDep) -> IngestProgressResponse:
    return service.get_ingest_progress()


@router.get("/ingest-snapshot", response_model=AdminIngestSnapshot)
def ingest_snapshot(service: AdminServiceDep) -> AdminIngestSnapshot:
    return service.get_admin_ingest_snapshot()


@router.get("/system-status", response_model=SystemStatusResponse)
def system_status(service: AdminServiceDep) -> SystemStatusResponse:
    return service.get_system_status()

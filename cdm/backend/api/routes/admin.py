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
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/ingest-progress", response_model=IngestProgressResponse)
def ingest_progress() -> IngestProgressResponse:
    return get_ingest_progress()


@router.get("/ingest-snapshot", response_model=AdminIngestSnapshot)
def ingest_snapshot() -> AdminIngestSnapshot:
    return get_admin_ingest_snapshot()


@router.get("/system-status", response_model=SystemStatusResponse)
def system_status() -> SystemStatusResponse:
    return get_system_status()

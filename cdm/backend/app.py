from elastic_transport import TransportError
from elasticsearch import ApiError
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cdm.backend.api.router import api_router
from cdm.backend.dependencies import ContainerDep
from cdm.backend.errors import (
    AnalysisNotBuiltError,
    APIErrorHandlers,
    EntityNotFoundError,
)
from cdm.config import get_config
from cdm.contracts.api import AnalysisErrorResponse, HealthResponse, ReadinessResponse
from cdm.contracts.queries import QueryReadError
from cdm.store.client import IncompleteSearchError, SearchConfigurationError

app = FastAPI(
    title="Congress Tracker API",
    description="Backend APIs for state/member timelines and profiles.",
    version="0.1.0",
    responses={
        503: {
            "model": AnalysisErrorResponse,
            "description": "Analysis not built or dependency unavailable",
        },
    },
)

app.add_exception_handler(EntityNotFoundError, APIErrorHandlers.missing)
app.add_exception_handler(QueryReadError, APIErrorHandlers.invalid_query)
app.add_exception_handler(AnalysisNotBuiltError, APIErrorHandlers.not_built)
for error in (
    ApiError,
    TransportError,
    SearchConfigurationError,
    IncompleteSearchError,
):
    app.add_exception_handler(error, APIErrorHandlers.unavailable)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_config().api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/ready")
def readiness(container: ContainerDep) -> ReadinessResponse:
    """Read API dependency readiness, not corpus coverage or analytics freshness."""
    container.elastic_client.options(
        request_timeout=container.config.api.readiness_timeout_secs,
        max_retries=0,
        retry_on_timeout=False,
    ).info()
    return ReadinessResponse(status="ready")

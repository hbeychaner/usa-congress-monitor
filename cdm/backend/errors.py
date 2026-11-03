"""Safe HTTP boundaries for known missing records and search dependencies."""

import logging

from fastapi import Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from cdm.contracts.analysis import AnalysisState
from cdm.contracts.api import AnalysisErrorResponse, ErrorResponse
from cdm.contracts.queries import QueryReadError

logger = logging.getLogger(__name__)


class EntityNotFoundError(ValueError):
    pass


class AnalysisNotBuiltError(RuntimeError):
    pass


class APIErrorHandlers:
    @staticmethod
    async def invalid_query(request: Request, exc: Exception) -> JSONResponse:
        if not isinstance(exc, QueryReadError):
            raise exc
        return await request_validation_exception_handler(
            request,
            RequestValidationError(
                [
                    {
                        "loc": ("query", exc.parameter),
                        "type": "value_error",
                        "msg": str(exc),
                    }
                ]
            ),
        )

    @staticmethod
    async def missing(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(detail=str(exc)).model_dump(
                mode="json", exclude_none=True
            ),
        )

    @staticmethod
    async def not_built(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=AnalysisErrorResponse(
                detail=str(exc), analysis_state=AnalysisState.NOT_BUILT
            ).model_dump(mode="json", exclude_none=True),
        )

    @staticmethod
    async def unavailable(_request: Request, exc: Exception) -> JSONResponse:
        logger.warning("Search dependency failed (%s)", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content=AnalysisErrorResponse(
                detail="Search service unavailable; please try again later.",
                analysis_state=AnalysisState.UNAVAILABLE,
            ).model_dump(mode="json"),
        )

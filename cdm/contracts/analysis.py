"""Availability and known model lineage, not freshness against source ingestion."""

from __future__ import annotations

from enum import StrEnum

from cdm.contracts.base import ResponseModel


class AnalysisState(StrEnum):
    AVAILABLE = "available"
    NOT_BUILT = "not_built"
    EMPTY = "empty"
    STALE = "stale"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"


class AnalysisStatus(ResponseModel):
    state: AnalysisState
    source_model_version: str | None = None
    published_model_version: str | None = None

    @classmethod
    def for_model(
        cls, source: str | None, published: str | None, has_results: bool
    ) -> AnalysisStatus:
        if source is None:
            state = AnalysisState.NOT_BUILT
        elif published is None:
            state = AnalysisState.UNKNOWN
        elif source != published:
            state = AnalysisState.STALE
        else:
            state = AnalysisState.AVAILABLE if has_results else AnalysisState.EMPTY
        return cls(
            state=state,
            source_model_version=source,
            published_model_version=published,
        )


class AnalysisResponse(ResponseModel):
    analysis: AnalysisStatus

"""Recorded origin of a label, independent of analysis availability."""

from enum import StrEnum

from cdm.contracts.base import ResponseModel


class LabelSource(StrEnum):
    UNKNOWN = "unknown"
    LLM = "llm"
    KEYWORDS = "keywords"
    LARGEST_TOPIC = "largest_topic"
    OVERRIDE = "override"
    DETERMINISTIC = "deterministic"


class LabelFallbackReason(StrEnum):
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"
    REQUEST_FAILED = "request_failed"
    INVALID_RESPONSE = "invalid_response"
    NAME_COLLISION = "name_collision"


class LabelProvenance(ResponseModel):
    label_source: LabelSource = LabelSource.UNKNOWN
    fallback_reason: LabelFallbackReason | None = None


class LabelResult(LabelProvenance):
    label: str

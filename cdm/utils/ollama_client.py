"""Chat client for the local Ollama server, shared by the topic and group namers."""

from __future__ import annotations

import logging
from enum import StrEnum

import requests
from pydantic import AliasPath, BaseModel, Field

from cdm.config import OllamaConfig
from cdm.contracts.labels import LabelFallbackReason, LabelResult, LabelSource

logger = logging.getLogger(__name__)


class OllamaRole(StrEnum):
    SYSTEM = "system"
    USER = "user"


class OllamaChatMessage(BaseModel):
    role: OllamaRole
    content: str


class OllamaOptions(BaseModel):
    temperature: float


class OllamaRequest(BaseModel):
    model: str
    stream: bool = False
    options: OllamaOptions
    messages: list[OllamaChatMessage]


class OllamaMessage(BaseModel):
    content: str = Field(strict=True, validation_alias=AliasPath("message", "content"))


class OllamaReply(BaseModel):
    content: str
    fallback_reason: LabelFallbackReason | None = None


class OllamaClient:
    def __init__(self, config: OllamaConfig) -> None:
        self.config = config

    def is_available(self) -> bool:
        try:
            requests.get(
                f"{self.config.ollama_url}/api/tags",
                timeout=self.config.ollama_probe_timeout_secs,
            ).raise_for_status()
        except requests.RequestException:
            return False
        return True

    def chat(self, system: str, user: str) -> OllamaReply:
        """Validate the reply and retain a safe failure category, never server text."""
        try:
            response = requests.post(
                f"{self.config.ollama_url}/api/chat",
                json=OllamaRequest(
                    model=self.config.ollama_model,
                    options=OllamaOptions(temperature=self.config.ollama_temperature),
                    messages=[
                        OllamaChatMessage(role=OllamaRole.SYSTEM, content=system),
                        OllamaChatMessage(role=OllamaRole.USER, content=user),
                    ],
                ).model_dump(mode="json"),
                timeout=self.config.ollama_timeout_secs,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("ollama request failed (%s)", type(exc).__name__)
            return OllamaReply(
                content="", fallback_reason=LabelFallbackReason.REQUEST_FAILED
            )
        try:
            return OllamaReply(
                content=OllamaMessage.model_validate(response.json()).content
            )
        except ValueError:
            logger.warning("ollama returned an invalid chat response")
            return OllamaReply(
                content="", fallback_reason=LabelFallbackReason.INVALID_RESPONSE
            )

    def label(
        self,
        system: str,
        user: str,
        fallback: LabelResult,
        *,
        max_words: int,
        strip_prefix: bool = True,
    ) -> LabelResult:
        reply = self.chat(system, user)
        cleaned = reply.content.strip().strip("\"'").rstrip(".").strip()
        if strip_prefix:
            _, _, tail = cleaned.rpartition(":")
            cleaned = (tail or cleaned).strip()
        words = cleaned.split()
        if reply.fallback_reason is None and 0 < len(words) <= max_words:
            return LabelResult(label=" ".join(words), label_source=LabelSource.LLM)
        reason = reply.fallback_reason or LabelFallbackReason.INVALID_RESPONSE
        logger.warning("ollama label fallback: %s", reason)
        return fallback.model_copy(update={"fallback_reason": reason})

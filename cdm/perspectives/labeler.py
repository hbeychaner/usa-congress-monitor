"""Names perspectives with the local Ollama model, falling back to keyword labels."""

from __future__ import annotations

from pydantic import BaseModel

from cdm.contracts.labels import LabelFallbackReason, LabelResult, LabelSource
from cdm.utils.ollama_client import OllamaClient
from cdm.utils.topic_terms import keyword_label


class PerspectiveLabelConfig(BaseModel):
    system_prompt: str = (
        "You name the policy approach shared by a group of US Congressional bills "
        "that all belong to one topic. Given the topic, distinctive phrases and "
        "sample bill titles, reply with ONLY a 2-6 word title in plain English, "
        "title case, no quotes, no trailing punctuation. Base the title mainly on "
        "the distinctive phrases, since titles are often vague acronyms. Describe what the bills "
        "do (for example funding, restricting, studying, protecting), not the "
        "topic itself. Use neutral wording that does not imply support or "
        "opposition."
    )
    max_words: int = 8
    title_chars: int = 160


class PerspectiveLabeler:
    """One short label per perspective; keywords when Ollama is absent or unusable."""

    def __init__(
        self,
        ollama: OllamaClient,
        *,
        enabled: bool = True,
        config: PerspectiveLabelConfig | None = None,
    ) -> None:
        self.ollama = ollama
        self.config = config or PerspectiveLabelConfig()
        self._fallback_reason = (
            LabelFallbackReason.DISABLED
            if not enabled
            else LabelFallbackReason.UNAVAILABLE
            if not ollama.is_available()
            else None
        )

    def label(self, topic: str, terms: list[str], titles: list[str]) -> LabelResult:
        keywords = keyword_label(terms)
        fallback = LabelResult(
            label=keywords or "General",
            label_source=LabelSource.KEYWORDS
            if keywords
            else LabelSource.DETERMINISTIC,
            fallback_reason=self._fallback_reason,
        )
        if self._fallback_reason is not None:
            return fallback
        samples = "\n".join(f"- {title[: self.config.title_chars]}" for title in titles)
        return self.ollama.label(
            self.config.system_prompt,
            f"Topic: {topic}\nDistinctive phrases: {', '.join(terms)}\n"
            f"Sample bills:\n{samples}\n\nApproach title:",
            fallback,
            max_words=self.config.max_words,
        )

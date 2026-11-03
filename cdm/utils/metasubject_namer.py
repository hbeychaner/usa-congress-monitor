"""Name metasubject groups with the local Ollama model."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from pydantic import BaseModel, Field

from cdm.contracts.labels import LabelFallbackReason, LabelResult, LabelSource
from cdm.utils.metasubjects import LargestTopicNamer, NamedGroup, TopicVector
from cdm.utils.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class MetasubjectLabelConfig(BaseModel):
    prompt_topics: int = 25
    max_words: int = 5
    example_topics: int = 15
    attempts: int = Field(default=2, gt=0)
    system_prompt: str = (
        "You name broad policy areas covering many US Congressional bill topics. "
        "Given the titles of the topics in one group, reply with ONLY a name of "
        "1-4 words in plain English, title case, no quotes, no trailing "
        "punctuation. Name the single policy area that covers most titles. Use "
        "neutral wording that does not imply support or opposition."
    )
    rename_prompt: str = (
        "You rename one broad US Congressional policy area. Other policy areas "
        "currently share its name, so it needs a more specific name that "
        "separates it from them. Given this group's topic titles and the "
        "topic titles of the other groups, reply with ONLY a name of 1-4 words "
        "in plain English, title case, no quotes, no trailing punctuation. The "
        "name must describe what is distinctive about THIS group and must not "
        "equal any name already in use. Use neutral wording."
    )


class OllamaMetasubjectNamer:
    """Asks Ollama for a group name; falls back to the largest topic's label."""

    def __init__(
        self, ollama: OllamaClient, config: MetasubjectLabelConfig | None = None
    ) -> None:
        self.ollama = ollama
        self.config = config or MetasubjectLabelConfig()
        self.fallback = LargestTopicNamer()

    def name(self, members: Sequence[TopicVector]) -> LabelResult:
        ranked = sorted(members, key=lambda topic: topic.size, reverse=True)
        titles = "\n".join(
            f"- {topic.label}" for topic in ranked[: self.config.prompt_topics]
        )
        return self.ollama.label(
            self.config.system_prompt,
            f"Topics:\n{titles}\n\nPolicy area:",
            self.fallback.name(members),
            max_words=self.config.max_words,
            strip_prefix=False,
        )


class OllamaNameDisambiguator:
    """Gives groups that share a name distinct, more specific names."""

    def __init__(
        self, ollama: OllamaClient, config: MetasubjectLabelConfig | None = None
    ) -> None:
        self.ollama = ollama
        self.config = config or MetasubjectLabelConfig()

    def rename(
        self, colliding: Sequence[NamedGroup], taken: set[str]
    ) -> dict[int, LabelResult]:
        used = set(taken)
        renamed: dict[int, LabelResult] = {}
        for group in colliding:
            others = [other for other in colliding if other is not group]
            name = self._name_for(group, others, used)
            renamed[group.metasubject_id] = name
            used.add(name.label.casefold())
        return renamed

    def _titles(self, group: NamedGroup) -> str:
        ranked = sorted(group.members, key=lambda topic: topic.size, reverse=True)
        return "\n".join(
            f"- {topic.label}" for topic in ranked[: self.config.example_topics]
        )

    def _name_for(
        self, group: NamedGroup, others: Sequence[NamedGroup], used: set[str]
    ) -> LabelResult:
        contrast = "\n\n".join(
            f"Other group {index}:\n{self._titles(other)}"
            for index, other in enumerate(others, start=1)
        )
        prompt = (
            f"Current shared name: {group.name}\n\nThis group:\n"
            f"{self._titles(group)}\n\n{contrast}\n\nMore specific name for this group:"
        )
        largest = LargestTopicNamer().name(group.members)
        fallback = LabelResult(
            label=f"{group.name}: {largest.label}",
            label_source=LabelSource.DETERMINISTIC,
            fallback_reason=LabelFallbackReason.NAME_COLLISION,
        )
        for _ in range(self.config.attempts):
            candidate = self.ollama.label(
                self.config.rename_prompt,
                prompt,
                fallback,
                max_words=self.config.max_words,
                strip_prefix=False,
            )
            if candidate.label_source != LabelSource.LLM:
                fallback = candidate
            elif candidate.label.casefold() not in used:
                return candidate
            else:
                fallback.fallback_reason = LabelFallbackReason.NAME_COLLISION
        logger.warning("metasubject name fallback: %s", fallback.fallback_reason)
        return fallback

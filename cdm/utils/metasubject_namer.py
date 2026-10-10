"""Name metasubject groups with the local Ollama model."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from cdm.utils.metasubjects import LargestTopicNamer, NamedGroup, TopicVector
from cdm.utils.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

PROMPT_TOPICS = 25
MAX_NAME_WORDS = 5

_SYSTEM_PROMPT = (
    "You name broad policy areas covering many US Congressional bill topics. "
    "Given the titles of the topics in one group, reply with ONLY a name of "
    "1-4 words in plain English, title case, no quotes, no trailing "
    "punctuation. Name the single policy area that covers most titles. Use "
    "neutral wording that does not imply support or opposition."
)


class OllamaMetasubjectNamer:
    """Asks Ollama for a group name; falls back to the largest topic's label."""

    def __init__(self, ollama: OllamaClient) -> None:
        self.ollama = ollama
        self.fallback = LargestTopicNamer()

    def name(self, members: Sequence[TopicVector]) -> str:
        ranked = sorted(members, key=lambda topic: topic.size, reverse=True)
        titles = "\n".join(f"- {topic.label}" for topic in ranked[:PROMPT_TOPICS])
        return self._ask(titles) or self.fallback.name(members)

    def _ask(self, titles: str) -> str:
        content = self.ollama.chat(_SYSTEM_PROMPT, f"Topics:\n{titles}\n\nPolicy area:")
        words = content.strip().strip("\"'").rstrip(".").split()
        return " ".join(words) if 0 < len(words) <= MAX_NAME_WORDS else ""


class OllamaNameDisambiguator:
    """Gives groups that share a name distinct, more specific names."""

    EXAMPLE_TOPICS = 15
    ATTEMPTS = 2

    _SYSTEM_PROMPT = (
        "You rename one broad US Congressional policy area. Other policy areas "
        "currently share its name, so it needs a more specific name that "
        "separates it from them. Given this group's topic titles and the "
        "topic titles of the other groups, reply with ONLY a name of 1-4 words "
        "in plain English, title case, no quotes, no trailing punctuation. The "
        "name must describe what is distinctive about THIS group and must not "
        "equal any name already in use. Use neutral wording."
    )

    def __init__(self, ollama: OllamaClient) -> None:
        self.ollama = ollama

    def rename(
        self, colliding: Sequence[NamedGroup], taken: set[str]
    ) -> dict[int, str]:
        used = set(taken)
        renamed: dict[int, str] = {}
        for group in colliding:
            others = [other for other in colliding if other is not group]
            name = self._name_for(group, others, used)
            renamed[group.metasubject_id] = name
            used.add(name.casefold())
        return renamed

    def _titles(self, group: NamedGroup) -> str:
        ranked = sorted(group.members, key=lambda topic: topic.size, reverse=True)
        return "\n".join(f"- {topic.label}" for topic in ranked[: self.EXAMPLE_TOPICS])

    def _name_for(
        self, group: NamedGroup, others: Sequence[NamedGroup], used: set[str]
    ) -> str:
        contrast = "\n\n".join(
            f"Other group {index}:\n{self._titles(other)}"
            for index, other in enumerate(others, start=1)
        )
        prompt = (
            f"Current shared name: {group.name}\n\nThis group:\n"
            f"{self._titles(group)}\n\n{contrast}\n\nMore specific name for this group:"
        )
        for _ in range(self.ATTEMPTS):
            words = (
                self.ollama.chat(self._SYSTEM_PROMPT, prompt)
                .strip()
                .strip("\"'")
                .rstrip(".")
                .split()
            )
            candidate = " ".join(words)
            if 0 < len(words) <= MAX_NAME_WORDS and candidate.casefold() not in used:
                return candidate
        largest = LargestTopicNamer().name(group.members)
        return f"{group.name}: {largest}"

"""Name metasubject groups with the local Ollama model."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from cdm.utils.metasubjects import LargestTopicNamer, TopicVector
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
        content = self.ollama.chat(
            _SYSTEM_PROMPT, f"Topics:\n{titles}\n\nPolicy area:"
        )
        words = content.strip().strip("\"'").rstrip(".").split()
        return " ".join(words) if 0 < len(words) <= MAX_NAME_WORDS else ""

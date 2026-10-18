"""Names perspectives with the local Ollama model, falling back to keyword labels."""

from __future__ import annotations

from cdm.utils.ollama_client import OllamaClient
from cdm.utils.topic_terms import keyword_label

SYSTEM_PROMPT = (
    "You name the policy approach shared by a group of US Congressional bills "
    "that all belong to one topic. Given the topic, distinctive phrases and "
    "sample bill titles, reply with ONLY a 2-6 word title in plain English, "
    "title case, no quotes, no trailing punctuation. Base the title mainly on "
    "the distinctive phrases, since titles are often vague acronyms. Describe what the bills "
    "do (for example funding, restricting, studying, protecting), not the "
    "topic itself. Use neutral wording that does not imply support or "
    "opposition."
)
MAX_WORDS = 8
TITLE_CHARS = 160


class PerspectiveLabeler:
    """One short label per perspective; keywords when Ollama is absent or unusable."""

    def __init__(self, ollama: OllamaClient, *, enabled: bool = True) -> None:
        self.ollama = ollama
        self.enabled = enabled and ollama.is_available()

    def label(self, topic: str, terms: list[str], titles: list[str]) -> str:
        fallback = keyword_label(terms) or "General"
        if not self.enabled:
            return fallback
        samples = "\n".join(f"- {title[:TITLE_CHARS]}" for title in titles)
        reply = self.ollama.chat(
            SYSTEM_PROMPT,
            f"Topic: {topic}\nDistinctive phrases: {', '.join(terms)}\n"
            f"Sample bills:\n{samples}\n\nApproach title:",
        )
        cleaned = reply.strip().strip("\"'").rstrip(".").strip()
        _, _, tail = cleaned.rpartition(":")
        words = (tail or cleaned).split()
        return " ".join(words) if 0 < len(words) <= MAX_WORDS else fallback

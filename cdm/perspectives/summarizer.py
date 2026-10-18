"""Summarizes what one group of bills in a topic emphasizes, using the local Ollama model."""

from __future__ import annotations

from cdm.utils.ollama_client import OllamaClient

SYSTEM_PROMPT = (
    "You summarize the legislative approach of a group of US Congressional bills "
    "that all belong to one topic. Given the topic, the group, its distinctive "
    "phrases and sample bill titles, reply with ONE plain-English sentence of at "
    "most 30 words saying what these bills emphasize, propose or prioritize. Base "
    "it mainly on the distinctive phrases, since titles are often vague acronyms. "
    "Use neutral wording that does not praise or criticize, never mention a party "
    "or person by name, and do not restate the topic name. Reply with the sentence only."
)
MAX_WORDS = 45
TITLE_CHARS = 160


class ApproachSummarizer:
    """One sentence per group of bills; empty when Ollama is absent or its reply is unusable."""

    def __init__(self, ollama: OllamaClient, *, enabled: bool = True) -> None:
        self.ollama = ollama
        self.enabled = enabled and ollama.is_available()

    def summarize(
        self, topic: str, group: str, terms: list[str], titles: list[str]
    ) -> str:
        if not self.enabled or not terms:
            return ""
        samples = "\n".join(f"- {title[:TITLE_CHARS]}" for title in titles)
        reply = self.ollama.chat(
            SYSTEM_PROMPT,
            f"Topic: {topic}\nGroup: {group}\nDistinctive phrases: {', '.join(terms)}\n"
            f"Sample bills:\n{samples}\n\nSummary sentence:",
        )
        sentence = " ".join(reply.strip().strip("\"'").split())
        return sentence if 0 < len(sentence.split()) <= MAX_WORDS else ""

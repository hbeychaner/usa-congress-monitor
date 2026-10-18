"""Summarizes what one group of bills in a topic emphasizes, using the local Ollama model."""

from __future__ import annotations

from cdm.utils.ollama_client import OllamaClient

SYSTEM_PROMPT = (
    "You summarize the legislative approach of a group of US Congressional bills "
    "that all belong to one topic. You get the topic, the group, the official "
    "subject areas its bills carry more often than the other group, a few "
    "distinctive phrases, and sample bill titles. Reply with ONE plain-English "
    "sentence of at most 30 words naming the specific policies, programs or "
    "problems these bills address. Ground every claim in the titles and subjects; "
    "phrases are only hints and may be noisy. Do not open with 'These bills', do "
    "not use vague words such as 'measures', 'prioritize' or 'enhance', stay "
    "neutral, never name a party or person, and do not restate the topic name. "
    "Reply with the sentence only."
)
MAX_WORDS = 45
TITLE_CHARS = 160


class ApproachSummarizer:
    """One sentence per group of bills; empty when Ollama is absent or its reply is unusable."""

    def __init__(self, ollama: OllamaClient, *, enabled: bool = True) -> None:
        self.ollama = ollama
        self.enabled = enabled and ollama.is_available()

    def summarize(
        self,
        topic: str,
        group: str,
        terms: list[str],
        subjects: list[str],
        titles: list[str],
    ) -> str:
        if not self.enabled or not (terms or subjects):
            return ""
        samples = "\n".join(f"- {title[:TITLE_CHARS]}" for title in titles)
        reply = self.ollama.chat(
            SYSTEM_PROMPT,
            f"Topic: {topic}\nGroup: {group}\nSubject areas: {', '.join(subjects)}\n"
            f"Distinctive phrases: {', '.join(terms)}\n"
            f"Sample bills:\n{samples}\n\nSummary sentence:",
        )
        sentence = " ".join(reply.strip().strip("\"'").split())
        return sentence if 0 < len(sentence.split()) <= MAX_WORDS else ""

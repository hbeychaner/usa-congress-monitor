"""Generate human-readable topic titles with a local Ollama model.

EMM-style explainability: instead of exposing c-TF-IDF keyword bags
("lee relief wife sun"), each topic gets a short editorial title derived
from its top words and most representative bill texts. Falls back to the
keyword label when Ollama is unreachable so training never fails on it.
"""

from __future__ import annotations

import logging

from cdm.utils.ollama_client import OllamaClient
from cdm.utils.topic_records import TopicSummaryRow

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You name clusters of US Congressional bills. Given keywords and sample "
    "bill texts, reply with ONLY a title of 2-6 words in plain English, "
    "title case, no quotes, no trailing punctuation. Do not mention "
    "Congress, bills, acts, or legislation in the title. Name the subject "
    "shared by ALL samples, not a detail of one. Use neutral wording that "
    "does not imply support or opposition. If the samples concern "
    "individual people or places (private relief, honorary namings, "
    "commemorations), ignore the specific names and title the kind of "
    "measure, e.g. 'Private Relief for Individuals' or 'Post Office Namings'."
)

PROMPT_KEYWORDS = 15
PROMPT_SAMPLES = 8
SAMPLE_CHARS = 220


def _prompt(top_words: list[str], docs: list[str]) -> str:
    samples = "\n".join(f"- {doc[:SAMPLE_CHARS]}" for doc in docs[:PROMPT_SAMPLES])
    return (
        f"Keywords: {', '.join(top_words[:PROMPT_KEYWORDS])}\n"
        f"Sample bills:\n{samples}\n\n"
        "Topic title:"
    )


def _clean_label(text: str) -> str:
    label = text.strip().strip('"').strip("'").rstrip(".").strip()
    # Models occasionally prefix "Topic title:" despite instructions.
    _, _, tail = label.rpartition(":")
    label = (tail or label).strip()
    words = label.split()
    if not words or len(words) > 8:
        return ""
    return " ".join(words)


class TopicLabeler:
    """Titles topics through Ollama; unusable or missing replies yield no label."""

    def __init__(self, ollama: OllamaClient) -> None:
        self.ollama = ollama

    def generate(self, top_words: list[str], representative_docs: list[str]) -> str:
        """One short title, or "" when unavailable/unusable."""
        reply = self.ollama.chat(_SYSTEM_PROMPT, _prompt(top_words, representative_docs))
        return _clean_label(reply)

    def label_topics(
        self,
        summaries: list[TopicSummaryRow],
        representative_docs: dict[int, list[str]],
    ) -> dict[int, str]:
        """Labels for every non-outlier topic; skips topics Ollama can't label."""
        if not self.ollama.is_available():
            logger.warning("ollama unreachable; using keyword labels")
            return {}
        labels: dict[int, str] = {}
        for topic in summaries:
            topic_id = topic.topic_id
            if topic_id == -1:
                continue
            label = self.generate(topic.top_words, representative_docs.get(topic_id, []))
            if label:
                labels[topic_id] = label
        return labels

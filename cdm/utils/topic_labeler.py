"""Generate human-readable topic titles with a local Ollama model.

EMM-style explainability: instead of exposing c-TF-IDF keyword bags
("lee relief wife sun"), each topic gets a short editorial title derived
from its top words and most representative bill texts. Falls back to the
keyword label when Ollama is unreachable so training never fails on it.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from cdm.contracts.labels import LabelFallbackReason, LabelResult, LabelSource
from cdm.utils.ollama_client import OllamaClient
from cdm.utils.topic_records import TopicSummaryRow
from cdm.utils.topic_terms import keyword_label, topic_label

logger = logging.getLogger(__name__)


class TopicLabelConfig(BaseModel):
    system_prompt: str = (
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
    prompt_keywords: int = 15
    prompt_samples: int = 8
    sample_chars: int = 220
    max_words: int = 8


class TopicLabeler:
    """Titles topics through Ollama with recorded keyword fallbacks."""

    def __init__(
        self, ollama: OllamaClient, config: TopicLabelConfig | None = None
    ) -> None:
        self.ollama = ollama
        self.config = config or TopicLabelConfig()

    def generate(
        self,
        top_words: list[str],
        representative_docs: list[str],
        *,
        fallback_label: str = "General",
    ) -> LabelResult:
        samples = "\n".join(
            f"- {doc[: self.config.sample_chars]}"
            for doc in representative_docs[: self.config.prompt_samples]
        )
        keywords = keyword_label(top_words)
        return self.ollama.label(
            self.config.system_prompt,
            f"Keywords: {', '.join(top_words[: self.config.prompt_keywords])}\n"
            f"Sample bills:\n{samples}\n\nTopic title:",
            LabelResult(
                label=keywords or fallback_label,
                label_source=LabelSource.KEYWORDS
                if keywords
                else LabelSource.DETERMINISTIC,
            ),
            max_words=self.config.max_words,
        )

    def label_topics(
        self,
        summaries: list[TopicSummaryRow],
        representative_docs: dict[int, list[str]],
    ) -> dict[int, LabelResult]:
        """Every non-outlier topic retains its label's actual origin."""
        available = self.ollama.is_available()
        if not available:
            logger.warning("ollama unreachable; using keyword labels")
        labels: dict[int, LabelResult] = {}
        for topic in summaries:
            topic_id = topic.topic_id
            if topic_id == -1:
                continue
            labels[topic_id] = (
                self.generate(
                    topic.top_words,
                    representative_docs.get(topic_id, []),
                    fallback_label=topic.label or topic_label(topic.name, topic_id),
                )
                if available
                else LabelResult(
                    label=topic.label
                    or keyword_label(topic.top_words)
                    or topic_label(topic.name, topic_id),
                    label_source=LabelSource.KEYWORDS
                    if topic.top_words
                    else LabelSource.DETERMINISTIC,
                    fallback_reason=LabelFallbackReason.UNAVAILABLE,
                )
            )
        return labels

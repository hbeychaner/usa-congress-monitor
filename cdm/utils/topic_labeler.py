"""Generate human-readable topic titles with a local Ollama model.

EMM-style explainability: instead of exposing c-TF-IDF keyword bags
("lee relief wife sun"), each topic gets a short editorial title derived
from its top words and most representative bill texts. Falls back to the
keyword label when Ollama is unreachable so training never fails on it.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import requests

import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You name clusters of US Congressional bills. Given keywords and sample "
    "bill texts, reply with ONLY a title of 2-6 words in plain English, "
    "title case, no quotes, no trailing punctuation. Do not mention "
    "Congress, bills, acts, or legislation in the title."
)


def _prompt(top_words: list[str], docs: list[str]) -> str:
    samples = "\n".join(f"- {doc[:300]}" for doc in docs[:4])
    return (
        f"Keywords: {', '.join(top_words[:10])}\n"
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


def generate_topic_label(
    top_words: list[str],
    representative_docs: list[str],
    *,
    timeout: float = 60.0,
) -> str:
    """One short title from Ollama, or "" when unavailable/unusable."""
    try:
        response = requests.post(
            f"{settings.OLLAMA_URL}/api/chat",
            json={
                "model": settings.OLLAMA_MODEL,
                "stream": False,
                "options": {"temperature": 0.2},
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": _prompt(top_words, representative_docs)},
                ],
            },
            timeout=timeout,
        )
        response.raise_for_status()
        content = (response.json().get("message") or {}).get("content") or ""
        return _clean_label(content)
    except (requests.RequestException, json.JSONDecodeError, ValueError) as exc:
        logger.warning("ollama labeling failed: %s", exc)
        return ""


def label_topics(
    summaries: list[dict[str, Any]],
    representative_docs: dict[int, list[str]],
) -> dict[int, str]:
    """Labels for every non-outlier topic; skips topics Ollama can't label."""
    labels: dict[int, str] = {}
    for topic in summaries:
        topic_id = int(topic["topic_id"])
        if topic_id == -1:
            continue
        label = generate_topic_label(
            topic.get("top_words") or [], representative_docs.get(topic_id, [])
        )
        if label:
            labels[topic_id] = label
    return labels

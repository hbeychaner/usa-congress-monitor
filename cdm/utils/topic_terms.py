"""Normalize BERTopic keyword lists so unigrams and bigrams don't repeat words."""

from __future__ import annotations

from collections.abc import Iterable


def dedupe_terms(terms: Iterable[str]) -> list[str]:
    """Drop repeats and terms whose words all appear in another, longer term."""
    unique = list(dict.fromkeys(term.strip().lower() for term in terms if term.strip()))
    token_sets = [set(term.split()) for term in unique]
    kept = []
    for index, term in enumerate(unique):
        tokens = token_sets[index]
        covered = any(
            other != index and tokens < token_sets[other] for other in range(len(unique))
        )
        if not covered:
            kept.append(term)
    return kept


def keyword_label(terms: Iterable[str], limit: int = 4) -> str:
    """Space-joined label from terms that each contribute at least one new word."""
    seen: set[str] = set()
    parts: list[str] = []
    for term in dedupe_terms(terms):
        new = [word for word in term.split() if word not in seen]
        if not new:
            continue
        seen.update(new)
        parts.append(" ".join(new))
        if len(parts) == limit:
            break
    return " ".join(parts)

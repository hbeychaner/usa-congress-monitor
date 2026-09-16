"""spaCy-backed lemmatization for OpenSearch ``*_lemma`` search fields."""

from __future__ import annotations

import logging
import threading
from collections.abc import Sequence
from typing import Any

logger = logging.getLogger(__name__)

SPACY_MODEL = "en_core_web_md"

_nlp: Any = None
_lock = threading.Lock()


def _get_nlp() -> Any:
    global _nlp
    if _nlp is None:
        with _lock:
            if _nlp is None:
                import spacy

                try:
                    # parser/ner are not needed for lemmas; md lemmatizer
                    # requires tok2vec + tagger + attribute_ruler.
                    _nlp = spacy.load(SPACY_MODEL, disable=["parser", "ner"])
                except OSError as exc:
                    raise RuntimeError(
                        f"spaCy model {SPACY_MODEL!r} is not installed; "
                        "run `uv sync` (the model wheel is pinned in "
                        "pyproject.toml/requirements.txt)"
                    ) from exc
    return _nlp


def lemmatize_texts(texts: Sequence[str]) -> list[str]:
    """Return whitespace-joined lowercase lemmas for each text."""
    if not texts:
        return []
    nlp = _get_nlp()
    # Very large bill texts can exceed spaCy's max_length; truncate rather
    # than fail — the head of the document still carries the topical signal.
    max_chars = int(nlp.max_length)
    results: list[str] = []
    for doc in nlp.pipe([(text or "")[:max_chars] for text in texts]):
        results.append(
            " ".join(
                token.lemma_.lower()
                for token in doc
                if token.lemma_
                and not (token.is_punct or token.is_space or token.is_stop)
            )
        )
    return results


def lemmatize_text(text: str) -> str:
    return lemmatize_texts([text])[0]


def try_lemmatize_query(text: str) -> str:
    """Best-effort query lemmatization; returns "" when unavailable."""
    if not text or not text.strip():
        return ""
    try:
        return lemmatize_text(text)
    except Exception:
        logger.warning("Query lemmatization unavailable; skipping lemma clauses")
        return ""

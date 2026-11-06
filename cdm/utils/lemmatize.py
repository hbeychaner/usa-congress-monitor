"""Memory-bounded spaCy lemmatization for search fields and query text."""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterable, Sequence
from typing import Protocol

import spacy
from spacy.language import Language

from cdm.config import LemmatizationConfig, get_config


class LanguageLoader(Protocol):
    def __call__(self, name: str, *, exclude: Iterable[str]) -> Language: ...


class SpacyLemmatizer:
    def __init__(
        self, settings: LemmatizationConfig, loader: LanguageLoader,
        logger: logging.Logger,
    ) -> None:
        self._settings = settings
        self._loader = loader
        self._logger = logger
        self._language: Language | None = None
        self._lock = threading.Lock()

    def _model(self) -> Language:
        if self._language is None:
            try:
                self._language = self._loader(
                    self._settings.spacy_model,
                    exclude=self._settings.lemma_excluded_components,
                )
            except OSError as exc:
                raise RuntimeError(
                    f"spaCy model {self._settings.spacy_model!r} is not installed; "
                    "run `uv sync` (the model wheel is pinned in "
                    "pyproject.toml/requirements.txt)"
                ) from exc
        return self._language

    def lemmatize(self, texts: Sequence[str]) -> list[str]:
        if not texts:
            return []
        with self._lock:
            model = self._model()
            maximum = min(model.max_length, self._settings.lemma_max_chars)
            # Only strings escape the zone; Docs and Tokens must not outlive it.
            with model.memory_zone():
                return [
                    " ".join(
                        token.lemma_.lower()
                        for token in doc
                        if token.lemma_
                        and not (token.is_punct or token.is_space or token.is_stop)
                    )
                    for doc in model.pipe(
                        ((text or "")[:maximum] for text in texts),
                        batch_size=self._settings.lemma_batch_size,
                    )
                ]

    def try_query(self, text: str) -> str:
        if not text or not text.strip():
            return ""
        try:
            return self.lemmatize([text])[0]
        except (RuntimeError, ImportError, ValueError):
            self._logger.warning("Query lemmatization unavailable; skipping lemma clauses")
            return ""


_default_lemmatizer: SpacyLemmatizer = SpacyLemmatizer(
    get_config().lemmatization, spacy.load, logging.getLogger(__name__),
)


def lemmatize_texts(texts: Sequence[str]) -> list[str]:
    return _default_lemmatizer.lemmatize(texts)


def lemmatize_text(text: str) -> str:
    return lemmatize_texts([text])[0]


def try_lemmatize_query(text: str) -> str:
    return _default_lemmatizer.try_query(text)

"""Learns which words and phrases recur across unrelated topics, and so are not subject matter."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import CountVectorizer

from cdm.config import PerspectiveConfig
from cdm.perspectives.lexicon import BoilerplateLexicon
from cdm.perspectives.terms import Tokenizer

Analyzer = Callable[[str], list[str]]


class BoilerplateLearner:
    """A term is boilerplate if it is prominent in many topics, or in a large share of all bills."""

    def __init__(self, config: PerspectiveConfig, base: Tokenizer) -> None:
        self.config = config
        self.base = base

    def learn(self, texts_by_topic: Mapping[int, Sequence[str]]) -> BoilerplateLexicon:
        topics = [
            texts
            for texts in texts_by_topic.values()
            if len(texts) >= self.config.perspective_boilerplate_min_topic_bills
        ]
        words = self._spread(self.base.words, topics, corpus_cap=True)
        phrases = self._spread(self.base.ngrams, topics, corpus_cap=False)
        learned = self.base.lexicon.with_terms(words, phrases)
        return learned.with_names(self._rare_names(topics))

    def _rare_names(self, topics: list[Sequence[str]]) -> frozenset[str]:
        """Member names that are not also everyday words, so phrases holding them are credits."""
        names = self.base.lexicon.person_names
        texts = [text for group in topics for text in group]
        if not names or not texts:
            return names
        vectorizer = CountVectorizer(
            analyzer=self.base.content_words,  # pyright: ignore[reportArgumentType]
            binary=True,
            vocabulary=sorted(names),
        )
        counts = csr_matrix(vectorizer.fit_transform(texts))
        share = np.asarray(counts.sum(axis=0)).ravel() / len(texts)
        common = share >= self.config.perspective_name_common_share
        return frozenset(name for name, flag in zip(sorted(names), common) if not flag)

    def _spread(
        self, analyzer: Analyzer, topics: list[Sequence[str]], *, corpus_cap: bool
    ) -> frozenset[str]:
        config = self.config
        texts = [text for group in topics for text in group]
        if not texts:
            return frozenset()
        owner = np.repeat(np.arange(len(topics)), [len(group) for group in topics])
        vectorizer = CountVectorizer(
            analyzer=analyzer,  # pyright: ignore[reportArgumentType]
            binary=True,
            min_df=config.perspective_boilerplate_min_docs,
        )
        matrix = csr_matrix(vectorizer.fit_transform(texts))
        membership = csr_matrix(
            (np.ones(len(texts)), (owner, np.arange(len(texts)))),
            shape=(len(topics), len(texts)),
        )
        counts = csr_matrix(membership @ matrix)
        sizes = np.array([len(group) for group in topics], dtype=np.float64)
        row_of = np.repeat(np.arange(len(topics)), np.diff(counts.indptr))
        columns = np.asarray(counts.indices)
        hits = np.asarray(counts.data, dtype=np.float64)
        present = hits >= config.perspective_boilerplate_min_docs
        prominent = present & (
            hits / sizes[row_of] >= config.perspective_boilerplate_topic_share
        )
        vocabulary = np.asarray(vectorizer.get_feature_names_out())
        width = len(vocabulary)
        prominent_in = np.bincount(columns[prominent], minlength=width) / len(topics)
        present_in = np.bincount(columns[present], minlength=width) / len(topics)
        flagged = (prominent_in >= config.perspective_boilerplate_topic_spread) | (
            present_in >= config.perspective_boilerplate_presence_spread
        )
        if corpus_cap:
            share = np.asarray(matrix.sum(axis=0)).ravel() / len(texts)
            flagged |= share >= config.perspective_boilerplate_corpus_share
        return frozenset(str(term) for term in vocabulary[flagged])

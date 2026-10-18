"""Distinctive bigrams for each group of documents, by smoothed log-odds z-scores."""

from __future__ import annotations

import itertools
import re
from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, CountVectorizer

from cdm.config import PerspectiveConfig
from cdm.perspectives.lexicon import BoilerplateLexicon
from cdm.utils.topic_modeler import ALPHA_TOKEN_PATTERN, BOILERPLATE_STOPWORDS

SEGMENT_BREAK = re.compile(r"[.;:!?]")
POOL = 3
TOKEN = re.compile(ALPHA_TOKEN_PATTERN)
ROMAN_NUMERAL = re.compile(r"^(?=[ivxlc]+$)c{0,3}(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})$")
# Bill-drafting and printing boilerplate that says how a bill is written, not what it does.
DRAFTING_STOPWORDS = frozenset(
    [
        "short",
        "cite",
        "introduce",
        "introduced",
        "refer",
        "referred",
        "doc",
        "session",
        "publishing",
        "printing",
        "assemble",
        "assembled",
        "congressional",
        "enact",
        "enacted",
        "enactment",
        "strike",
        "insert",
        "subsection",
        "paragraph",
        "subparagraph",
        "clause",
        "indent",
        "redesignate",
        "amend",
        "follow",
        "new",
        "term",
        "mean",
        "include",
        "respect",
        "appropriate",
        "carry",
        "general",
        "head",
        "purpose",
        "house",
        "senate",
        "representatives",
        "america",
        "committee",
        "government",
        "office",
        "bills",
        "motion",
        "debatable",
        "debate",
        "debated",
        "joint",
        "disapproval",
        "disapprove",
        "notwithstanding",
        "sponsor",
        "sponsors",
        "respectively",
        "dispose",
        "disposed",
        "procedure",
        "procedures",
        "month",
        "months",
        "date",
        "dates",
        "day",
        "days",
        "later",
        "calendar",
        "stat",
        "september",
        "january",
        "february",
        "march",
        "april",
        "june",
        "july",
        "august",
        "october",
        "november",
        "december",
        "sentence",
        "proviso",
        "comply",
        "compliance",
        "equally",
        "divide",
        "reconsider",
        "waive",
        "intervene",
        "recognition",
        "referral",
        "discharge",
        "paygo",
        "previous",
        "question",
        "opponent",
        "designee",
        "constitutional",
        "disagree",
        "proceed",
        "adoption",
        "passage",
        "leader",
        "standing",
        "exercise",
        "rulemake",
        "attest",
        "clerk",
    ]
)
STOP_WORDS = frozenset(
    ENGLISH_STOP_WORDS.union(BOILERPLATE_STOPWORDS).union(DRAFTING_STOPWORDS)
)


class Tokenizer:
    """Splits text into content words and phrases, minus fixed and corpus-learned boilerplate."""

    def __init__(self, lexicon: BoilerplateLexicon, max_ngram: int = 3) -> None:
        self.lexicon = lexicon
        self.max_ngram = max_ngram

    @staticmethod
    def content_words(text: str) -> list[str]:
        """Lowercase words without fixed stop words or roman-numeral list markers."""
        return [
            word
            for word in TOKEN.findall(text.lower())
            if word not in STOP_WORDS and not ROMAN_NUMERAL.match(word)
        ]

    def words(self, text: str) -> list[str]:
        return [
            word for word in self.content_words(text) if word not in self.lexicon.words
        ]

    def terms(self, text: str) -> list[str]:
        """Single words and phrases together, for weighting a bill against its topic."""
        return self.words(text) + self.ngrams(text)

    def ngrams(self, text: str) -> list[str]:
        """Runs of 2 to max_ngram adjacent content words, never spanning a sentence break."""
        phrases: list[str] = []
        for segment in SEGMENT_BREAK.split(text):
            tokens = self.content_words(segment)
            for size in range(2, self.max_ngram + 1):
                for start in range(len(tokens) - size + 1):
                    run = tokens[start : start + size]
                    if self._keeps(run):
                        phrases.append(" ".join(run))
        return phrases

    def _keeps(self, run: list[str]) -> bool:
        lexicon = self.lexicon
        for first, second in itertools.pairwise(run):
            if first == second:
                return False
            if first in lexicon.person_names and second in lexicon.person_names:
                return False
            if self._is_sponsor_line(first, second) or self._is_sponsor_line(
                second, first
            ):
                return False
        if any(word in lexicon.words for word in run):
            return False
        return " ".join(run) not in lexicon.phrases

    def _is_sponsor_line(self, name: str, place: str) -> bool:
        """A member name beside a state, as in a sponsor credit."""
        return name in self.lexicon.person_names and place in self.lexicon.place_names


class DistinctiveTerms:
    """Ranks phrases a group uses more than the other groups, not merely often."""

    def __init__(self, config: PerspectiveConfig, tokenizer: Tokenizer) -> None:
        self.config = config
        self.tokenizer = tokenizer

    def matching(
        self, texts: Sequence[str], terms: Sequence[str], limit: int
    ) -> list[int]:
        """Positions of the texts that use the most of the given phrases."""
        wanted = set(terms)
        scores = [len(wanted.intersection(self.tokenizer.ngrams(t))) for t in texts]
        ranked = sorted(range(len(texts)), key=lambda i: scores[i], reverse=True)
        return [position for position in ranked[:limit] if scores[position] > 0]

    def top(
        self, texts: Sequence[str], groups: NDArray[np.intp]
    ) -> dict[int, list[str]]:
        vectorizer = CountVectorizer(
            analyzer=self.tokenizer.ngrams,  # pyright: ignore[reportArgumentType]
            min_df=self.config.perspective_term_min_docs,
            binary=True,
        )
        try:
            matrix = vectorizer.fit_transform(texts)
        except ValueError:
            return {int(group): [] for group in np.unique(groups)}
        vocabulary = vectorizer.get_feature_names_out()
        total = np.asarray(matrix.sum(axis=0)).ravel().astype(np.float64)  # pyright: ignore[reportAttributeAccessIssue]
        prior = total + 1.0
        prior_sum = prior.sum()
        result: dict[int, list[str]] = {}
        for group in np.unique(groups):
            inside = np.asarray(matrix[groups == group].sum(axis=0)).ravel()
            outside = total - inside
            in_prior = inside + prior
            out_prior = outside + prior
            in_rest = inside.sum() + prior_sum - in_prior
            out_rest = outside.sum() + prior_sum - out_prior
            delta = np.log(in_prior / in_rest) - np.log(out_prior / out_rest)
            score = delta / np.sqrt(1.0 / in_prior + 1.0 / out_prior)
            score[inside < self.config.perspective_term_min_docs] = -np.inf
            pool = np.argsort(score)[::-1][: self.config.perspective_top_terms * POOL]
            ranked = [str(vocabulary[p]) for p in pool if score[p] > 0]
            result[int(group)] = self._longest(ranked)[
                : self.config.perspective_top_terms
            ]
        return result

    @staticmethod
    def _longest(ranked: list[str]) -> list[str]:
        """Drops a phrase when a longer ranked phrase already contains it."""
        padded = [f" {term} " for term in ranked]
        return [
            term
            for term, mine in zip(ranked, padded)
            if not any(mine != other and mine in other for other in padded)
        ]

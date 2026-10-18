"""Backs each distinctive phrase and subject with the bills and sponsors behind it."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

import numpy as np

from cdm.config import PerspectiveConfig
from cdm.perspectives.models import BillRef, PerspectiveBill, SubjectUse, TermUse
from cdm.perspectives.terms import Tokenizer

SMOOTHING = 1.0
MIN_SHARED_WORDS = 3


class TermEvidence:
    """Counts bills and sponsors per phrase and drops phrases too thinly supported."""

    def __init__(self, config: PerspectiveConfig, tokenizer: Tokenizer) -> None:
        self.config = config
        self.tokenizer = tokenizer

    def describe(
        self, terms: Sequence[str], bills: Sequence[PerspectiveBill]
    ) -> list[TermUse]:
        wanted = set(terms)
        users: dict[str, list[PerspectiveBill]] = {term: [] for term in terms}
        for bill in bills:
            for term in wanted.intersection(self.tokenizer.ngrams(bill.text)):
                users[term].append(bill)
        config = self.config
        described: list[TermUse] = []
        seen: set[frozenset[str]] = set()
        for term in terms:
            using = users[term]
            words = frozenset(term.split())
            # Word-order variants such as 'disaster declaration' and 'declaration disaster' are one idea.
            if words in seen:
                continue
            sponsors = {bill.sponsor_id for bill in using if bill.sponsor_id}
            if (
                len(using) < config.perspective_term_min_docs
                or len(sponsors) < config.perspective_term_min_sponsors
            ):
                continue
            seen.add(words)
            described.append(
                TermUse(
                    term=term,
                    bills=len(using),
                    sponsors=len(sponsors),
                    examples=[
                        BillRef(doc_id=bill.doc_id, title=bill.title)
                        for bill in using[: config.perspective_term_examples]
                    ],
                )
            )
        return described[: config.perspective_top_terms]


class SubjectContrast:
    """Ranks the CRS subjects one group's bills carry more often than the rest's."""

    def __init__(self, config: PerspectiveConfig) -> None:
        self.config = config

    def top(
        self, inside: Sequence[PerspectiveBill], outside: Sequence[PerspectiveBill]
    ) -> list[SubjectUse]:
        counted = Counter(name for bill in inside for name in set(bill.subjects))
        others = Counter(name for bill in outside for name in set(bill.subjects))
        scored: list[tuple[float, SubjectUse]] = []
        for name, hits in counted.items():
            if hits < self.config.perspective_subject_min_bills:
                continue
            rest = others.get(name, 0)
            delta = np.log(
                (hits + SMOOTHING) / (len(inside) - hits + SMOOTHING)
            ) - np.log((rest + SMOOTHING) / (len(outside) - rest + SMOOTHING))
            error = np.sqrt(1 / (hits + SMOOTHING) + 1 / (rest + SMOOTHING))
            if delta > 0:
                scored.append(
                    (
                        float(delta / error),
                        SubjectUse(name=name, bills=hits, share=hits / len(inside)),
                    )
                )
        scored.sort(key=lambda pair: pair[0], reverse=True)
        kept: list[SubjectUse] = []
        for _, use in scored:
            if len(kept) == self.config.perspective_subjects_top:
                break
            if not any(self._same_idea(use.name, other.name) for other in kept):
                kept.append(use)
        return kept

    @staticmethod
    def _same_idea(first: str, second: str) -> bool:
        """True when one subject is the other plus trailing words, as in 'Housing ... funding'."""
        left, right = first.lower().split(), second.lower().split()
        shorter, longer = sorted((left, right), key=len)
        return (
            len(shorter) >= MIN_SHARED_WORDS
            and longer[: len(shorter)] == shorter
            or left == right
        )

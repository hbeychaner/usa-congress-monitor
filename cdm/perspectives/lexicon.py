"""Terms the corpus itself shows to be boilerplate rather than subject matter."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BoilerplateLexicon:
    words: frozenset[str] = frozenset()
    phrases: frozenset[str] = frozenset()
    person_names: frozenset[str] = frozenset()
    place_names: frozenset[str] = frozenset()

    def with_names(self, person_names: frozenset[str]) -> BoilerplateLexicon:
        return BoilerplateLexicon(
            self.words, self.phrases, person_names, self.place_names
        )

    def with_terms(
        self, words: frozenset[str], phrases: frozenset[str]
    ) -> BoilerplateLexicon:
        return BoilerplateLexicon(words, phrases, self.person_names, self.place_names)

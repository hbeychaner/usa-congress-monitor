from unittest.mock import MagicMock

import numpy as np
from elasticsearch import Elasticsearch

from cdm.config import PerspectiveConfig
from cdm.graph.models import PartyGroup
from cdm.perspectives.corpus import BipartisanVoteReader, MeasureFilter
from cdm.perspectives.evidence import SubjectContrast, TermEvidence
from cdm.perspectives.lexicon import BoilerplateLexicon
from cdm.perspectives.models import PerspectiveBill
from cdm.perspectives.terms import DistinctiveTerms, Tokenizer


def test_measure_filter_drops_resolutions_and_ceremonial_titles() -> None:
    measures = MeasureFilter(PerspectiveConfig())

    assert measures.is_policy("hr", "Border Security Enhancement Act")
    assert not measures.is_policy("HRES", "Providing for consideration of H.R. 1")
    assert not measures.is_policy(
        "hr", "To designate a facility as the Main Street Post Office"
    )


def test_ngrams_do_not_cross_sentence_breaks_or_repeat_words() -> None:
    tokenizer = Tokenizer(BoilerplateLexicon(), max_ngram=3)

    phrases = tokenizer.ngrams(
        "Lawful permanent resident status. Border wall wall funding"
    )

    assert "lawful permanent resident" in phrases
    assert "resident border" not in phrases
    assert "wall wall" not in phrases


def test_learned_boilerplate_is_dropped_from_words_but_not_content_words() -> None:
    tokenizer = Tokenizer(BoilerplateLexicon(words=frozenset({"grants"})))

    assert "grants" in tokenizer.content_words("housing grants")
    assert tokenizer.words("housing grants") == ["housing"]


def test_distinctive_terms_prefer_the_longest_phrase() -> None:
    assert DistinctiveTerms._longest(["wear camera", "body wear camera", "grant"]) == [
        "body wear camera",
        "grant",
    ]


def test_distinctive_terms_rank_each_groups_own_language() -> None:
    config = PerspectiveConfig()
    terms = DistinctiveTerms(config, Tokenizer(BoilerplateLexicon(), 2))
    texts = ["solar tax credit expansion"] * 6 + [
        "firearm background check enforcement"
    ] * 6
    groups = np.array([0] * 6 + [1] * 6, dtype=np.intp)

    top = terms.top(texts, groups)

    assert any("solar" in term for term in top[0])
    assert any("firearm" in term for term in top[1])


def _bill(doc_id: str, sponsor: str, text: str, subjects: list[str]) -> PerspectiveBill:
    return PerspectiveBill(
        doc_id=doc_id, title=doc_id, text=text, sponsor_id=sponsor, subjects=subjects
    )


def test_stem_folds_plurals() -> None:
    assert Tokenizer.stem("tribes") == "tribe"
    assert Tokenizer.stem("utilities") == "utility"
    assert Tokenizer.stem("class") == "class"
    assert Tokenizer.stem("status") == "status"


def test_rare_member_names_are_dropped_from_phrases() -> None:
    lexicon = BoilerplateLexicon(person_names=frozenset({"kevin"}))
    tokenizer = Tokenizer(lexicon)

    assert tokenizer.ngrams("pass kevin") == []
    assert tokenizer.ngrams("solar credit") == ["solar credit"]


def test_term_evidence_requires_several_sponsors() -> None:
    config = PerspectiveConfig()
    evidence = TermEvidence(config, Tokenizer(BoilerplateLexicon(), 2))
    broad = [_bill(f"b{i}", f"s{i}", "solar credit", []) for i in range(6)]
    narrow = [_bill(f"n{i}", "only", "wind lease", []) for i in range(6)]

    described = evidence.describe(["solar credit", "wind lease"], broad + narrow)

    assert [use.term for use in described] == ["solar credit"]
    assert described[0].bills == 6
    assert described[0].sponsors == 6
    assert len(described[0].examples) == config.perspective_term_examples


def test_subject_contrast_ranks_each_groups_own_subjects() -> None:
    contrast = SubjectContrast(PerspectiveConfig())
    left = [
        _bill(f"l{i}", f"s{i}", "", ["Native Americans", "Energy"]) for i in range(6)
    ]
    right = [_bill(f"r{i}", f"t{i}", "", ["Public Lands", "Energy"]) for i in range(6)]

    names = [use.name for use in contrast.top(left, right)]

    assert names == ["Native Americans"]


def test_subject_contrast_merges_near_duplicate_subjects() -> None:
    contrast = SubjectContrast(PerspectiveConfig())
    names = [
        "Housing and Community Development",
        "Housing and community development funding",
    ]
    left = [_bill(f"l{i}", f"s{i}", "", names) for i in range(6)]
    right = [_bill(f"r{i}", f"t{i}", "", ["Public Lands"]) for i in range(6)]

    assert len(contrast.top(left, right)) == 1


def _vote_reader() -> BipartisanVoteReader:
    parties = {
        "D1": PartyGroup.DEMOCRATIC,
        "D2": PartyGroup.DEMOCRATIC,
        "D3": PartyGroup.DEMOCRATIC,
        "R1": PartyGroup.REPUBLICAN,
        "R2": PartyGroup.REPUBLICAN,
        "R3": PartyGroup.REPUBLICAN,
    }
    return BipartisanVoteReader(
        MagicMock(spec=Elasticsearch), parties, PerspectiveConfig()
    )


def test_vote_is_bipartisan_when_most_of_both_parties_say_yea() -> None:
    assert _vote_reader().backed_by_both(["D1", "D2", "R1", "R2"], ["D3", "R3"])


def test_vote_is_partisan_when_one_party_mostly_opposes() -> None:
    assert not _vote_reader().backed_by_both(["R1", "R2", "R3", "D1"], ["D2", "D3"])


def test_vote_without_both_parties_is_not_bipartisan() -> None:
    assert not _vote_reader().backed_by_both(["R1", "R2"], [])

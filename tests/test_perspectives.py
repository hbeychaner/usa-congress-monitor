import numpy as np

from cdm.config import PerspectiveConfig
from cdm.perspectives.corpus import MeasureFilter
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

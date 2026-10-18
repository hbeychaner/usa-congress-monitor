from cdm.config import PerspectiveConfig
from cdm.perspectives.corpus import MeasureFilter
from cdm.perspectives.lexicon import BoilerplateLexicon
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
    groups = [0] * 6 + [1] * 6

    top = terms.top(texts, groups)

    assert any("solar" in term for term in top[0])
    assert any("firearm" in term for term in top[1])

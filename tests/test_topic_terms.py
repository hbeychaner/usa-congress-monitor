from cdm.utils.topic_terms import dedupe_terms, keyword_label


def test_dedupe_drops_covered_unigrams_and_repeats():
    terms = ["equal access", "access", "equal", "access justice", "Equal Access"]
    assert dedupe_terms(terms) == ["equal access", "access justice"]


def test_keyword_label_has_no_repeated_words():
    label = keyword_label(["equal access", "access", "access justice", "legal aid"])
    assert label == "equal access justice legal aid"
    assert len(label.split()) == len(set(label.split()))

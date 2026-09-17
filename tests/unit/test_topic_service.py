from cdm.backend.services.topic_service import _quarter, topic_label


def test_topic_label_strips_leading_id():
    assert topic_label("5_health_care_medicare", 5) == "health care medicare"


def test_topic_label_outlier():
    assert topic_label("-1_the_of", -1) == "Uncategorized"


def test_topic_label_fallbacks():
    assert topic_label(None, 7) == "Topic 7"
    assert topic_label("plain", 3) == "plain"


def test_quarter_bins():
    assert _quarter("2025-01-15") == "2025-Q1"
    assert _quarter("2025-12-31") == "2025-Q4"

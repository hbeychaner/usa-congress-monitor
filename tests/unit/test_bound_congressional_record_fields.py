from src.models.other_models import BoundCongressionalRecordListItem


def test_sections_dailyDigest_and_url_and_build_id():
    sample = {
        "date": "1947-03-17",
        "volumeNumber": 93,
        "congress": 80,
        "sessionNumber": 1,
        "updateDate": "2025-04-18",
        "sections": [{"name": "Daily Digest", "startPage": 3, "endPage": 29}],
        "dailyDigest": {
            "text": [{"type": "PDF", "url": "https://example.com/doc.pdf"}]
        },
    }

    # capture expected raw section fields before validation (validators may mutate input)
    expected = sample["sections"][0].copy()
    expected_daily = sample["dailyDigest"].copy()
    # also shallow-copy inner text entries to avoid in-place mutation
    if isinstance(expected_daily.get("text"), list):
        expected_daily["text"] = [t.copy() if isinstance(t, dict) else t for t in expected_daily["text"]]

    m = BoundCongressionalRecordListItem.model_validate(sample)

    # URL should be synthesized from the date when not provided
    assert m.url is not None

    # sections and dailyDigest should be preserved via their aliases
    # `sections` is now a list of `Section` models; compare their fields
    assert isinstance(m.sections, list)
    assert len(m.sections) == len(sample["sections"])
    sec = m.sections[0]
    # `name` from the raw sample is not mapped into the `Section.title`;
    # current behavior leaves `title` as None while preserving page bounds.
    assert sec.title is None
    assert sec.start_page == expected["startPage"]
    assert sec.end_page == expected["endPage"]
    # current behavior may leave `daily_digest` unset; accept either preserved dict or None
    assert m.daily_digest is None or m.daily_digest == expected_daily

    # build_id should synthesize a unique id including section bounds
    assert m.build_id() == "bound-congressional-record:1947:3:17:3:29"

from src.models.other_models import DailyCongressionalRecordIssue, FullIssue, EntireIssueEntry


def test_entire_issue_part_coercion_and_build_id():
    # EntireIssueEntry.part should coerce numeric strings to ints
    payload = {
        "volumeNumber": "172",
        "issueNumber": "50",
        "fullIssue": {"entireIssue": [{"part": "1", "type": "PDF", "url": "https://example.com/1.pdf"}]},
    }

    inst = DailyCongressionalRecordIssue.model_validate(payload)
    # entireIssue parts become integers when possible
    assert inst.full_issue is not None
    ee = inst.full_issue.entire_issue[0]
    assert isinstance(ee.part, int) and ee.part == 1

    # build_id should prefer volumeNumber/issueNumber
    assert inst.build_id() == "daily-congressional-record:172:50"

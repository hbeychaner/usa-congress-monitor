from src.models.other_models import BoundCongressionalRecordListItem


def test_bound_record_build_id_from_date_and_url_synthesis():
    b = BoundCongressionalRecordListItem(date="1947-03-17T00:00:00")
    # `build_id()` should produce a deterministic id from the date
    assert b.build_id() == "bound-congressional-record:1947:3:17"

    # The model validator should synthesize a reasonable API URL when missing
    assert (
        str(b.url)
        == "https://api.congress.gov/v3/bound-congressional-record/1947/3/17?format=json"
    )

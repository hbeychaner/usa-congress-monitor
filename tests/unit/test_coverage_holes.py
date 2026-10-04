from datetime import UTC, datetime, timedelta

from cdm.workers import tasks


def _at(day: int) -> datetime:
    return datetime(2026, 8, day, tzinfo=UTC)


def test_interior_hole_and_stale_tail_are_found():
    intervals = [(_at(1), _at(5)), (_at(9), _at(12))]
    holes = tasks._coverage_holes(intervals, _at(1), _at(20))
    assert holes == [(_at(5), _at(9)), (_at(12), _at(20))]


def test_fully_covered_and_fresh_has_no_holes():
    intervals = [(_at(1), _at(10)), (_at(8), _at(19))]
    assert tasks._coverage_holes(intervals, _at(1), _at(20)) == []


def test_spans_are_chunked_to_a_week():
    chunks = tasks._chunk_span(_at(1), _at(1) + timedelta(days=15))
    assert [end - start for start, end in chunks] == [
        timedelta(days=7),
        timedelta(days=7),
        timedelta(days=1),
    ]

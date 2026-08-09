import pytest

from scripts.ingest_history import _year_window


def test_year_window_supports_boundary_overlap():
    assert _year_window(2024, overlap_days=1) == (
        "2023-12-31T00:00:00Z",
        "2025-01-01T23:59:59Z",
    )


def test_year_window_rejects_negative_overlap():
    with pytest.raises(ValueError, match="non-negative"):
        _year_window(2024, overlap_days=-1)
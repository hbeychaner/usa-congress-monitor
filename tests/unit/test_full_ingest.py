from datetime import date

import pytest

from cdm.ingest.full_ingest import FullIngestConfig, plan_full_ingest, smoke_job


def test_full_plan_covers_static_date_and_congress_scopes() -> None:
    config = FullIngestConfig(
        first_congress=118,
        last_congress=119,
        start_date=date(2024, 1, 1),
        end_date=date(2025, 1, 1),
        window_days=365,
    )

    jobs = plan_full_ingest(config)
    labels = {job.label for job in jobs}

    assert "static:congress" in labels
    assert "date:amendment:2024-01-01:2024-12-30" in labels
    assert "date:amendment:2024-12-31:2025-01-01" in labels
    assert "congress:law:118" in labels
    assert "congress:law:119" in labels
    assert all(job.payload["force_item_fetch"] is True for job in jobs)


def test_smoke_job_is_bounded() -> None:
    job = smoke_job(FullIngestConfig())

    assert job.label == "smoke:congress"
    assert job.payload["resources"] == ["congress"]
    assert job.payload["max_pages"] == 1
    assert job.payload["max_items"] == 1
    assert job.payload["fetch_items"] is False


@pytest.mark.parametrize(
    ("field", "value"),
    [("window_days", 0), ("concurrency", 0), ("index_batch_size", 0)],
)
def test_full_config_rejects_non_positive_values(field: str, value: int) -> None:
    with pytest.raises(ValueError):
        FullIngestConfig(**{field: value})

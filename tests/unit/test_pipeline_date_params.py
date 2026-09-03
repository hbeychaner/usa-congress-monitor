from pathlib import Path

from cdm.ingest.pipeline import Pipeline, PipelineConfig
from cdm.ingest.resource_config import RESOURCE_CONFIGS
from cdm.ingest.runner import Resource, _normalize_api_datetime


def test_normalize_api_datetime_removes_fractional_seconds():
    assert _normalize_api_datetime("2026-08-28T07:21:49.330791Z") == (
        "2026-08-28T07:21:49Z"
    )


def test_pipeline_passes_configured_date_parameter_names(monkeypatch, tmp_path):
    captured = {}

    class RunnerStub:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run(self):
            return {"list_count": 0, "item_count": 0}

    monkeypatch.setattr("cdm.ingest.pipeline.IngestRunner", RunnerStub)
    config = PipelineConfig(
        outdir=Path(tmp_path),
        from_date="2025-01-01T00:00:00Z",
        to_date="2025-01-31T23:59:59Z",
    )

    Pipeline(config).run([Resource.BILL])

    bill_config = RESOURCE_CONFIGS[Resource.BILL]
    assert captured["from_date_param"] == bill_config.from_date_param
    assert captured["to_date_param"] == bill_config.to_date_param
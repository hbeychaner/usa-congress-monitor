from pathlib import Path

from cdm.ingest.pipeline import Pipeline, PipelineConfig
from cdm.ingest.resource_config import RESOURCE_CONFIGS
from cdm.ingest.runner import Resource


def test_pipeline_passes_configured_date_parameter_names(monkeypatch, tmp_path):
    captured = {}

    class RunnerStub:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run(self):
            return None

    monkeypatch.setattr("cdm.ingest.pipeline.IngestRunner", RunnerStub)
    config = PipelineConfig(
        outdir=Path(tmp_path),
        from_date="2025-01-01T00:00:00Z",
        to_date="2025-01-31T23:59:59Z",
    )

    Pipeline(config).run([Resource.AMENDMENT])

    amendment_config = RESOURCE_CONFIGS[Resource.AMENDMENT]
    assert captured["from_date_param"] == amendment_config.from_date_param
    assert captured["to_date_param"] == amendment_config.to_date_param
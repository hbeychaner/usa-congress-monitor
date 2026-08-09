from cdm.ingest.pipeline import PipelineConfig
from cdm.ingest.runner import Resource
from scripts.ingest_history import _checkpoint_matches, _checkpoint_parameters


def test_checkpoint_matches_same_chunk_parameters(tmp_path):
    config = PipelineConfig(
        outdir=tmp_path,
        from_date="2024-01-01T00:00:00Z",
        to_date="2024-12-31T23:59:59Z",
    )
    state = {
        "label": "year=2024",
        "status": "completed",
        "resources": ["amendment"],
        "parameters": _checkpoint_parameters(config),
    }

    assert _checkpoint_matches(state, "year=2024", [Resource.AMENDMENT], config)


def test_checkpoint_rejects_changed_parameters(tmp_path):
    config = PipelineConfig(
        outdir=tmp_path,
        from_date="2024-01-01T00:00:00Z",
        to_date="2024-12-31T23:59:59Z",
    )
    state = {
        "label": "year=2024",
        "status": "completed",
        "resources": ["amendment"],
        "parameters": {
            "from_date": "2023-01-01T00:00:00Z",
            "to_date": "2023-12-31T23:59:59Z",
            "congress": None,
        },
    }

    assert not _checkpoint_matches(state, "year=2024", [Resource.AMENDMENT], config)


def test_failed_checkpoint_does_not_match(tmp_path):
    config = PipelineConfig(outdir=tmp_path, congress=118)
    state = {
        "label": "congress=118",
        "status": "failed",
        "resources": ["law"],
        "parameters": _checkpoint_parameters(config),
    }

    assert not _checkpoint_matches(state, "congress=118", [Resource.LAW], config)


def test_checkpoint_rejects_different_resource_set(tmp_path):
    config = PipelineConfig(outdir=tmp_path, congress=118)
    state = {
        "label": "congress=118",
        "status": "completed",
        "resources": ["law"],
        "parameters": _checkpoint_parameters(config),
    }

    assert not _checkpoint_matches(
        state, "congress=118", [Resource.LAW, Resource.CONGRESS], config
    )
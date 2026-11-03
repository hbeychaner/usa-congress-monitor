import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel


class ReadImports(BaseModel):
    modules: list[str]


class TestReadBoundary:
    def test_fresh_api_and_submission_imports_do_not_load_training(self) -> None:
        source = """
import json
import sys
from cdm.backend.app import app
from scripts import train_topic_model, build_member_graph, build_perspectives
print(json.dumps({"modules": list(sys.modules)}))
"""
        result = subprocess.run(
            [sys.executable, "-W", "error::UserWarning", "-c", source],
            cwd=Path(__file__).resolve().parents[2],
            text=True,
            capture_output=True,
            check=True,
            timeout=60,
        )
        imported = set(ReadImports.model_validate_json(result.stdout).modules)
        assert not imported.intersection(
            {
                "bertopic",
                "sentence_transformers",
                "scipy",
                "sklearn",
                "cdm.workers.runtime",
                "cdm.topics.training",
                "cdm.graph.job",
                "cdm.perspectives.job",
            }
        )

"""Ensure local startup has a reachable Ollama server and installed label model."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdm.config import get_config
from cdm.deployment.ollama import OllamaStartup


class OllamaCommand:
    def run(self) -> None:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--check-only", action="store_true")
        args = parser.parse_args()
        config = get_config().ollama
        try:
            with requests.Session() as session:
                OllamaStartup(config, session).ensure(check_only=args.check_only)
        except (RuntimeError, OSError, subprocess.SubprocessError, requests.RequestException) as exc:
            parser.exit(1, f"Ollama readiness failed ({type(exc).__name__}): {exc}\n")
        print(f"Ollama ready; label model {config.ollama_model!r} is installed.")


if __name__ == "__main__":
    OllamaCommand().run()

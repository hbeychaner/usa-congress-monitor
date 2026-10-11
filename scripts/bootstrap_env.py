"""Create the local .env from .env.example and mint the OpenSearch API key."""

from __future__ import annotations

import argparse
import secrets
import sys
from enum import StrEnum
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PATH = REPO_ROOT / ".env.example"
ENV_PATH = REPO_ROOT / ".env"
COMPOSE_ENV_LINK = REPO_ROOT / "elastic-start-local" / ".env"
API_KEY_NAME = "congress-tracker"
REQUEST_TIMEOUT_SECS = 30


class Command(StrEnum):
    INIT = "init"
    API_KEY = "api-key"


class EnvFile:
    """Minimal KEY=value dotenv editor that preserves unrelated lines."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lines = path.read_text().splitlines()

    def get(self, key: str) -> str:
        for line in self.lines:
            name, sep, value = line.partition("=")
            if sep and name.strip() == key:
                return value.strip().strip('"')
        return ""

    def set(self, key: str, value: str) -> None:
        for index, line in enumerate(self.lines):
            if line.partition("=")[0].strip() == key:
                self.lines[index] = f"{key}={value}"
                return
        self.lines.append(f"{key}={value}")

    def save(self) -> None:
        self.path.write_text("\n".join(self.lines) + "\n")


class EnvBootstrapper:
    """Prepares a fresh checkout for `make local` and ingestion."""

    GENERATED_SECRETS = ("ES_LOCAL_PASSWORD", "KIBANA_LOCAL_PASSWORD", "KIBANA_ENCRYPTION_KEY")

    def init(self) -> None:
        if not ENV_PATH.exists():
            ENV_PATH.write_text(EXAMPLE_PATH.read_text())
            env = EnvFile(ENV_PATH)
            for key in self.GENERATED_SECRETS:
                if not env.get(key):
                    env.set(key, secrets.token_hex(16))
            env.save()
            print(f"Created {ENV_PATH.name}; set CONGRESS_API_KEY before ingesting.")
        if not COMPOSE_ENV_LINK.exists():
            COMPOSE_ENV_LINK.symlink_to(Path("..") / ENV_PATH.name)

    def create_api_key(self) -> None:
        env = EnvFile(ENV_PATH)
        url = env.get("ES_LOCAL_URL") or "http://localhost:9200"
        response = requests.post(
            f"{url}/_security/api_key",
            auth=("elastic", env.get("ES_LOCAL_PASSWORD")),
            json={"name": API_KEY_NAME},
            timeout=REQUEST_TIMEOUT_SECS,
        )
        response.raise_for_status()
        encoded = str(response.json()["encoded"])
        env.set("ES_LOCAL_API_KEY", encoded)
        env.set("ELASTIC_API_KEY", encoded)
        env.save()
        print("Wrote ES_LOCAL_API_KEY and ELASTIC_API_KEY to .env")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", type=Command, choices=list(Command))
    command = parser.parse_args().command
    bootstrapper = EnvBootstrapper()
    if command is Command.INIT:
        bootstrapper.init()
    else:
        bootstrapper.create_api_key()
    return 0


if __name__ == "__main__":
    sys.exit(main())

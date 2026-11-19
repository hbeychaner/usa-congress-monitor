"""Start the native local Ollama service and verify the configured label model."""

from __future__ import annotations

import platform
import shutil
import subprocess
import time
from urllib.parse import urlsplit

import requests
from pydantic import BaseModel

from cdm.config import OllamaConfig


class ModelRequest(BaseModel):
    model: str


class OllamaStartup:
    def __init__(self, config: OllamaConfig, session: requests.Session) -> None:
        self._config = config
        self._session = session

    def _available(self) -> bool:
        try:
            response = self._session.get(
                f"{self._config.ollama_url.rstrip('/')}/api/version",
                timeout=self._config.ollama_probe_timeout_secs,
            )
        except (requests.ConnectionError, requests.Timeout):
            return False
        response.raise_for_status()
        return True

    def ensure(self, *, check_only: bool = False) -> None:
        if not self._available():
            if check_only:
                raise RuntimeError("Ollama is unreachable from the application container.")
            self._start()
            deadline = time.monotonic() + self._config.ollama_timeout_secs
            while not self._available():
                if time.monotonic() >= deadline:
                    raise RuntimeError("Timed out waiting for the native Ollama service.")
                time.sleep(1)
        response = self._session.post(
            f"{self._config.ollama_url.rstrip('/')}/api/show",
            json=ModelRequest(model=self._config.ollama_model).model_dump(mode="json"),
            timeout=self._config.ollama_probe_timeout_secs,
        )
        if response.status_code == 404:
            raise RuntimeError(
                f"Ollama model {self._config.ollama_model!r} is missing. "
                "Run `ollama pull` with that model on the Ollama server, then retry."
            )
        response.raise_for_status()

    def _start(self) -> None:
        endpoint = urlsplit(self._config.ollama_url)
        if (
            endpoint.scheme != "http"
            or endpoint.hostname not in {"localhost", "127.0.0.1", "::1"}
            or endpoint.port != 11434
            or endpoint.path not in {"", "/"}
        ):
            raise RuntimeError(
                "Configured Ollama endpoint is unreachable. Start that server "
                "and verify OLLAMA_URL; only the default local endpoint is auto-started."
            )
        if platform.system() == "Darwin":
            if shutil.which("brew") and subprocess.run(
                ["brew", "list", "--formula", "ollama"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                check=False, timeout=30,
            ).returncode == 0:
                command = ["brew", "services", "start", "ollama"]
            else:
                command = ["open", "-gj", "-a", "Ollama"]
        elif platform.system() == "Linux":
            command = ["systemctl", "--user", "start", "ollama"]
        else:
            raise RuntimeError("Start the native Ollama application, then retry.")
        subprocess.run(command, check=True, timeout=60)

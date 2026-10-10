"""Chat client for the local Ollama server, shared by the topic and group namers."""

from __future__ import annotations

import json
import logging

import requests

from cdm.config import OllamaConfig

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self, config: OllamaConfig) -> None:
        self.config = config

    def is_available(self) -> bool:
        try:
            requests.get(
                f"{self.config.ollama_url}/api/tags",
                timeout=self.config.ollama_probe_timeout_secs,
            ).raise_for_status()
        except requests.RequestException:
            return False
        return True

    def chat(self, system: str, user: str) -> str:
        """The model's reply, or "" when the server fails or answers unusably."""
        try:
            response = requests.post(
                f"{self.config.ollama_url}/api/chat",
                json={
                    "model": self.config.ollama_model,
                    "stream": False,
                    "options": {"temperature": self.config.ollama_temperature},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
                timeout=self.config.ollama_timeout_secs,
            )
            response.raise_for_status()
            return (response.json().get("message") or {}).get("content") or ""
        except (requests.RequestException, json.JSONDecodeError, ValueError) as exc:
            logger.warning("ollama request failed: %s", exc)
            return ""
